"""Pipeline de produção (orquestração). Gera 1 slot: versículo -> LLM -> eval ->
imagem/TTS/montagem -> pacote pronto. O CLI (factory/cli.py) chama isto."""
import json
import os
import random
import unicodedata
import uuid
from datetime import datetime, timezone

from . import content, evaluation
from ..adapters import images, store, tts, video
from ..config import path

_GREETINGS = ("bom dia", "boa tarde", "boa noite")
_SEP = " \t,.!;:—–-"  # separadores/pontuação a limpar após a saudação
_WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
             "sexta-feira", "sábado", "domingo"]


def weekday_pt(date_str: str) -> str:
    """Dia da semana em PT-BR a partir de AAAA-MM-DD (data da publicação)."""
    try:
        return _WEEKDAYS[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except ValueError:
        return ""


def _slug(s: str) -> str:
    """'quinta-feira' -> 'quintafeira' (p/ hashtag, sem acento/hífen)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def _compose_hashtags(cfg, slot: str, weekday: str) -> list:
    """~5 hashtags p/ a legenda (não p/ a tela): tag(s) do tipo + 1 ampla + nicho sorteado.
    Pesquisa 2026: 3-5 é o ideal. Período -> #bomdia/#boatarde/#boanoite;
    dia da semana -> #feliz<dia> + #<dia> (ex: #felizquintafeira #quintafeira)."""
    hc = cfg.get("hashtags", {})
    broad, niche = hc.get("broad", []), hc.get("niche", [])
    target = hc.get("total", 5)
    slot_cfg = cfg["slots"][slot]
    if slot_cfg.get("weekday") and weekday:
        slot_tags = ["#feliz" + _slug(weekday), "#" + _slug(weekday)]
    elif slot_cfg.get("hashtag"):
        slot_tags = [slot_cfg["hashtag"]]
    else:
        slot_tags = []
    n_niche = max(0, target - 1 - len(slot_tags))      # resto após tipo + 1 ampla
    tags = slot_tags + ([random.choice(broad)] if broad else [])
    tags += random.sample(niche, min(n_niche, len(niche)))
    seen, out = set(), []                              # dedup preservando ordem
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _strip_greeting(frase: str) -> str:
    """Remove uma saudação no início da frase (defensivo contra 'Boa tarde, boa tarde').
    Trata tanto 'Boa tarde! ...' quanto a saudação tecida ('Boa tarde com ...')."""
    s = frase.lstrip()
    for g in _GREETINGS:
        if s.lower().startswith(g):
            rest = s[len(g):].lstrip(_SEP)
            return rest[:1].upper() + rest[1:] if rest else frase
    return frase


def run_slot(cfg, niche: str, slot: str, date_str: str, voice: dict = None) -> dict:
    run_id = uuid.uuid4().hex[:12]
    ts = datetime.now(timezone.utc).isoformat()
    out_dir = path("output", date_str, slot)
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n=== {slot} ({run_id}) ===")

    # 1. versículo verbatim do dataset
    verse = content.select_unused_verse(cfg, slot)
    print(f"  versículo: {verse['ref']}")

    # saudação: o slot do dia da semana usa "Feliz <dia>"; os demais usam a
    # saudação fixa SEM mencionar o dia.
    slot_cfg = cfg["slots"][slot]
    weekday = weekday_pt(date_str)
    if slot_cfg.get("weekday"):
        greeting = f"Feliz {weekday}" if weekday else "Olá"
    else:
        greeting = slot_cfg["greeting"]
    spoken_greeting = f"{greeting}!"

    # 2. LLM call #1: k variações de gancho/frase/cta/caption
    k = cfg["eval"]["k"]
    variants = content.generate_frames(cfg, slot, verse, k, greeting)

    # 3. hard checks (pré-vídeo): versículo verbatim
    hc = evaluation.hard_checks(cfg, slot, verse)
    if not hc["pass"]:
        print(f"  HARD FAIL: {hc}")
        return _record(cfg, niche, slot, run_id, ts, verse, variants,
                       {"variants": [], "chosen_idx": None, "verdict": "FAIL"}, hc, out_dir, None)

    # 4. LLM-judge: pass@k -> escolhe a melhor frase
    jr = evaluation.judge(cfg, slot, verse, variants)
    chosen = jr.get("chosen_idx")
    print(f"  judge: {jr.get('verdict')} (chosen={chosen})")
    if jr.get("verdict") != "PASS" or chosen is None:
        return _record(cfg, niche, slot, run_id, ts, verse, variants, jr, hc, out_dir, None)

    chosen_variant = variants[chosen]
    gancho = _strip_greeting(chosen_variant.get("gancho", "")).strip()
    chosen_variant["frase"] = _strip_greeting(chosen_variant["frase"])
    cta = (chosen_variant.get("cta") or "").strip()
    # locução: gancho -> saudação -> frase -> versículo
    narration = (f"{gancho}. {spoken_greeting} {chosen_variant['frase']} "
                 f"Como diz a Palavra: {verse['text']}")

    # 5-7. voz (atribuída pelo batch p/ não repetir no dia; senão sorteia) -> imagem -> tts
    if voice is None:
        voice = tts.pick_voice(cfg)
    print(f"  voz: {voice['name']} ({voice['gender']})")
    imgs = images.fetch_images(cfg["slots"][slot]["image_query"],
                               cfg["video"].get("images", 1), out_dir)
    voice_path = tts.tts(narration, os.path.join(out_dir, "voice.mp3"), cfg, voice["id"])
    track = video.pick_music(cfg)
    if track:
        print(f"  música: {os.path.basename(track)}")
    print(f"  gancho: {gancho}")
    # scrim escalonado por slot (manhã mais leve, noite mais escuro)
    cfg["overlay"]["scrim"] = cfg["slots"][slot].get("scrim", cfg["overlay"].get("scrim", 0.4))
    # beats de texto: gancho (prende) -> versículo (mensagem) -> CTA (na cauda)
    vdur = video._audio_duration(voice_path)
    hook_end = min(3.5, max(2.5, vdur * 0.3))
    # referência separada por 2 linhas em branco -> destaque de qual é o versículo
    beats = [{"text": gancho, "start": 0.0, "end": hook_end},
             {"text": f"{greeting}\n\n{verse['text']}\n\n\n{verse['ref']}",
              "start": hook_end, "end": vdur}]
    if cta:
        beats.append({"text": cta, "start": vdur, "end": None})  # cauda
    vid = video.assemble(imgs, voice_path, beats, os.path.join(out_dir, "video.mp4"), cfg, music=track)

    # 8. hard checks (pós-vídeo): formato
    hc_video = evaluation.hard_checks(cfg, slot, verse, video_path=vid)
    print(f"  vídeo: {vid}  formato_ok={hc_video['pass']}")

    # 9. pacote pronto (hashtags curadas: tag do tipo + 1 ampla + nicho)
    hashtags = _compose_hashtags(cfg, slot, weekday)
    _write_package(out_dir, slot, greeting, verse, chosen_variant, voice, track, hashtags)
    return _record(cfg, niche, slot, run_id, ts, verse, variants, jr, hc_video, out_dir, chosen)


def _write_package(out_dir, slot, greeting, verse, variant, voice, track, hashtags):
    # legenda e hashtags em arquivos SEPARADOS (hashtags vão só na legenda do post,
    # nunca no texto do vídeo).
    with open(os.path.join(out_dir, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(variant["caption"])
    with open(os.path.join(out_dir, "hashtags.txt"), "w", encoding="utf-8") as f:
        f.write(" ".join(hashtags))
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({
            "slot": slot, "greeting": greeting, "verse_ref": verse["ref"],
            "verse_text": verse["text"],
            "gancho": variant.get("gancho", ""), "frase": variant["frase"],
            "cta": variant.get("cta", ""),
            "caption": variant["caption"], "hashtags": hashtags,
            "voice": voice["name"], "voice_id": voice["id"],
            "music": os.path.basename(track) if track else None,
        }, f, ensure_ascii=False, indent=2)


def _record(cfg, niche, slot, run_id, ts, verse, variants, jr, hc, out_dir, chosen):
    ch = evaluation.content_hash(verse["ref"], variants[chosen]["frase"] if chosen is not None else "")
    row = {
        "run_id": run_id, "ts": ts, "niche": niche, "slot": slot,
        "verse_ref": verse["ref"], "verse_text": verse["text"],
        "frame_variants": [v["frase"] for v in variants],
        "judge_scores": jr.get("variants", []),
        "chosen_idx": chosen, "hard_checks": hc,
        "judge_verdict": jr.get("verdict", "FAIL"),
        "judge_reasons": json.dumps(jr.get("variants", []), ensure_ascii=False),
        "human_verdict": None,
        "prompt_version": cfg["eval"]["prompt_version"],
        "rubric_version": evaluation.rubric_version(cfg),
        "model_id": os.getenv("CLAUDE_MODEL", "claude-code-subscription"),
        "content_hash": ch,
    }
    store.record_eval(row)
    # Só marca versículo como usado se o pacote foi de fato produzido (PASS).
    if chosen is not None and jr.get("verdict") == "PASS":
        store.mark_used(verse["ref"], run_id, ts)
    return {"run_id": run_id, "verdict": jr.get("verdict"), "out_dir": out_dir}


def run_batch(cfg, niche: str, date_str: str, only_slot: str = None) -> list:
    """Roda os slots do dia, com vozes distintas (sorteia sem repetir entre slots)."""
    store.init()
    slots = [only_slot] if only_slot else list(cfg["slots"].keys())
    pool = cfg["tts"]["voices"]
    if len(slots) > 1 and len(pool) >= len(slots):
        voice_map = dict(zip(slots, random.sample(pool, len(slots))))
    else:
        voice_map = {}
    results = []
    for slot in slots:
        try:
            res = run_slot(cfg, niche, slot, date_str, voice=voice_map.get(slot))
            print(f"  -> {res}")
            results.append(res)
        except Exception as e:  # noqa: BLE001 — loga e segue p/ próximo slot
            print(f"  ERRO em {slot}: {e}")
    return results
