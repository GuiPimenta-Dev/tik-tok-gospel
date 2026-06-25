"""Adapter de vídeo: render de texto (Pillow) + montagem (ffmpeg) + seleção de música.

Motor B (assembly). Texto via PNG transparente + `overlay` (ffmpeg local não tem
`drawtext`). N fotos com crossfade + zoom, scrim constante, beats de texto com fade.
"""
from __future__ import annotations

import os
import random
import re
import subprocess

from ..config import path

# Emojis/símbolos que a fonte não tem glifo (viram "tofu" □) — removidos do texto na tela.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF\U0000FE00-\U0000FE0F\U0000200D\U000024C2\U00002700-\U000027BF]+",
    flags=re.UNICODE)


def _strip_emoji(s: str) -> str:
    s = _EMOJI.sub("", s)
    s = re.sub(r"[ \t]{2,}", " ", s)        # colapsa espaços/tabs — PRESERVA quebras de linha
    return "\n".join(line.strip() for line in s.split("\n")).strip()


def _audio_duration(audio_path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def pick_music(cfg) -> str | None:
    """Sorteia 1 faixa do pool (None se desabilitado ou pasta vazia)."""
    if not cfg["music"].get("enabled", True):
        return None
    music_dir = path(cfg["music"]["dir"])
    if not os.path.isdir(music_dir):
        return None
    tracks = [f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".m4a", ".wav"))]
    return os.path.join(music_dir, random.choice(tracks)) if tracks else None


def render_scrim_png(cfg, out_png: str) -> str:
    """Scrim de tela cheia (escurece a foto uniformemente) — overlay CONSTANTE."""
    from PIL import Image
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    a = int(255 * float(cfg.get("overlay", {}).get("scrim", 0.0)))
    Image.new("RGBA", (w, h), (0, 0, 0, a)).save(out_png)
    return out_png


def render_text_png(text: str, cfg, out_png: str) -> str:
    """Renderiza SÓ o texto (+ halo) num PNG transparente full-frame. O scrim é
    separado (render_scrim_png) p/ poder ter beats de texto com fade sem piscar o fundo.
    """
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

    w, h = cfg["video"]["width"], cfg["video"]["height"]
    fc = cfg["font"]
    ov = cfg.get("overlay", {})
    stroke = 3
    margin = 90
    max_w = w - 2 * margin
    font = ImageFont.truetype(path(fc["path"]), fc["size"])

    text = _strip_emoji(text)                       # fonte não renderiza emoji (tofu)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))   # base transparente (sem scrim)
    measure = ImageDraw.Draw(img)

    # Quebra por parágrafo (\n) e depois por palavra, respeitando a largura útil.
    lines = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        cur = ""
        for word in para.split():
            trial = (cur + " " + word).strip()
            bb = measure.textbbox((0, 0), trial, font=font, stroke_width=stroke)
            if (bb[2] - bb[0]) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)

    asc, desc = font.getmetrics()
    line_h, spacing = asc + desc, 18
    block_h = len(lines) * line_h + max(0, len(lines) - 1) * spacing
    y0 = (h - block_h) // 2

    box_a = int(255 * float(ov.get("box_alpha", 0.0)))
    if box_a > 0:
        pad = 70
        rect = [margin - pad, y0 - pad, w - margin + pad, y0 + block_h + pad]
        if ov.get("gradient"):
            # Halo escuro suave atrás do texto (borrado = cinematográfico).
            halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(halo).rounded_rectangle(rect, radius=80, fill=(0, 0, 0, box_a))
            img = Image.alpha_composite(img, halo.filter(ImageFilter.GaussianBlur(55)))
        else:
            ImageDraw.Draw(img).rounded_rectangle(rect, radius=30, fill=(0, 0, 0, box_a))

    draw = ImageDraw.Draw(img)
    y = y0
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        x = (w - (bb[2] - bb[0])) // 2
        draw.text((x, y), line, font=font, fill=fc.get("color", "white"),
                  stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        y += line_h + spacing

    img.save(out_png)
    return out_png


def _zoompan(idx: int, w: int, h: int, fps: int, frames: int, zoom: bool) -> str:
    """Filtro de 1 imagem: cobre o frame vertical + (opcional) zoom lento."""
    base = f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if zoom:
        base += f",zoompan=z='min(zoom+0.0004,1.4)':d={frames}:s={w}x{h}:fps={fps}"
    else:
        base += f",loop=loop={frames}:size=1:start=0,fps={fps}"
    return f"{base},setsar=1,format=yuv420p,setpts=PTS-STARTPTS[v{idx}]"


def _build_image_graph(n: int, w: int, h: int, fps: int, dur: float, T: float, zoom: bool):
    """Grafo do fundo: n imagens com zoom + crossfade -> [bg] (sem texto)."""
    L = (dur + (n - 1) * T) / n if n > 1 else dur   # duração por imagem
    Lf = int(L * fps)
    chains = [_zoompan(i, w, h, fps, Lf, zoom) for i in range(n)]
    if n == 1:
        chains.append("[v0]null[bg]")
    else:
        prev, cum = "v0", L
        for i in range(1, n):
            out = "bg" if i == n - 1 else f"x{i}"
            chains.append(f"[{prev}][v{i}]xfade=transition=fade:duration={T}:offset={cum - T:.3f}[{out}]")
            prev, cum = out, cum + L - T
    return chains


def assemble(images, voice: str, beats, out_path: str, cfg,
             zoom: bool = True, music: str = None) -> str:
    """Monta o vídeo: n imagens (crossfade+zoom) + scrim constante + beats de texto
    cronometrados (gancho -> versículo -> CTA) com fade + voz (+ música).
    `beats` = lista de {text, start, end}. Fallback p/ sem-zoom se o zoom falhar."""
    if isinstance(images, str):
        images = [images]
    if isinstance(beats, str):                       # compat: 1 texto p/ todo o vídeo
        beats = [{"text": beats, "start": 0.0, "end": None}]
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    tail = float(cfg["video"].get("tail", 4.0))
    maxs = float(cfg["video"].get("max_seconds", 30))
    narr = _audio_duration(voice)
    dur = min(narr + tail, maxs)                        # teto rígido (ex: 30s)
    tail_actual = max(0.5, dur - narr)                  # cauda real (encolhe se bater no teto)
    af, vf, fd = min(2.0, tail_actual), min(1.2, tail_actual), 0.4   # fades áudio/vídeo/texto
    T = float(cfg["video"].get("crossfade", 1.0))
    n = len(images)
    if music is None:
        music = pick_music(cfg)
    for b in beats:                                  # 'end' None = até o fim
        if b.get("end") is None:
            b["end"] = dur

    # Faixas calmas têm intro fraca/fade-in -> a música "parece" começar tarde.
    # Entra no miolo (volume cheio desde o 1º segundo) e ainda varia a parte tocada.
    music_args = []
    if music:
        mdur = _audio_duration(music)
        if mdur > dur + 2:
            headroom = mdur - dur - 1.0
            off = random.uniform(8.0, min(25.0, headroom)) if headroom > 9 else 0.0
            music_args = ["-ss", f"{off:.2f}", "-i", music]
        else:
            music_args = ["-stream_loop", "-1", "-i", music]   # faixa curta: loopa

    scrim_png = out_path + ".scrim.png"
    render_scrim_png(cfg, scrim_png)
    beat_pngs = []
    for i, b in enumerate(beats):
        p = f"{out_path}.t{i}.png"
        render_text_png(b["text"], cfg, p)
        beat_pngs.append(p)

    def run(use_zoom):
        chains = _build_image_graph(n, w, h, fps, dur, T, use_zoom)
        chains.append(f"[bg][{n}:v]overlay=0:0[base]")        # scrim constante (input n)
        prev = "base"
        for i, b in enumerate(beats):
            idx = n + 1 + i                                   # pngs de texto
            s, e = b["start"], b["end"]
            chains.append(f"[{idx}:v]format=rgba,fade=t=in:st={s:.2f}:d={fd}:alpha=1,"
                          f"fade=t=out:st={max(s, e - fd):.2f}:d={fd}:alpha=1[txt{i}]")
            out = f"o{i}"
            chains.append(f"[{prev}][txt{i}]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'[{out}]")
            prev = out
        chains.append(f"[{prev}]fade=t=out:st={dur - vf:.2f}:d={vf:.2f}[vout]")

        voice_idx = n + 1 + len(beats)
        vdb = cfg.get("audio", {}).get("voice_db", 0)
        vfilt = f"volume={vdb}dB" if vdb else "anull"
        if music:
            gain = cfg["music"]["volume_db"]
            chains.append(f"[{voice_idx}:a]{vfilt}[vc];"
                          f"[{voice_idx + 1}:a]volume={gain}dB[m];"
                          f"[vc][m]amix=inputs=2:duration=longest:dropout_transition=0[mix];"
                          f"[mix]afade=t=out:st={dur - af:.2f}:d={af:.2f}[a]")
        else:
            chains.append(f"[{voice_idx}:a]{vfilt},apad,afade=t=out:st={dur - af:.2f}:d={af:.2f}[a]")

        cmd = ["ffmpeg", "-y"]
        for img in images:
            cmd += ["-i", img]
        cmd += ["-loop", "1", "-i", scrim_png]
        for p in beat_pngs:
            cmd += ["-loop", "1", "-i", p]
        cmd += ["-i", voice]
        cmd += music_args
        cmd += ["-filter_complex", ";".join(chains), "-map", "[vout]", "-map", "[a]",
                "-t", f"{dur:.2f}", "-r", str(fps),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", out_path]
        subprocess.run(cmd, check=True, capture_output=True)

    try:
        run(zoom)
    except subprocess.CalledProcessError:
        if zoom:
            run(False)
        else:
            raise
    finally:
        for p in [scrim_png, *beat_pngs]:
            if os.path.exists(p):
                os.remove(p)
    return out_path
