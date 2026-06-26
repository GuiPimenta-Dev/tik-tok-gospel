"""Monta uma PASTA de revisão/entrega de um intervalo de vídeos.

  output/_packages/gospel | DD-MM-AAAA - DD-MM-AAAA/   <- ÚNICO artefato da run
    ├── index.html                 -> folha (preview + copiar caption+hashtags)
    ├── DD-MM-AAAA/                 -> 1 pasta por dia
    │     manha.mp4  tarde.mp4  noite.mp4  <dia-da-semana>.mp4   (só os vídeos, nomeados por slot)
    └── .meta/                      -> oculto: legenda+hashtags p/ reconstruir o index

O pipeline gera num diretório de trabalho OCULTO e temporário (output/.work), que é
apagado no fim — então output/ só mostra a coleção, sem pastas de dia soltas. O bundle é
autossuficiente (vídeos + .meta). Pasta do dia = só os 4 vídeos, pra ela achar e postar
fácil no TikTok; a legenda+hashtags ela copia no index.html (botão "Copiar legenda").
"""
import html
import json
import os
import shutil
import unicodedata
from datetime import datetime
from itertools import groupby

from ..config import path

_SLOT_ORDER = ["manha", "tarde", "noite", "semana"]
_SLOT_LABEL = {"manha": "🌅 Manhã · ~7h", "tarde": "☀️ Tarde · ~12h",
               "noite": "🌙 Noite · ~20h", "semana": "📅 Dia da semana · ~8h"}
_WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
             "sexta-feira", "sábado", "domingo"]


def _read(p: str) -> str:
    return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""


def _fmt(date_str: str, sep: str = "/") -> str:
    y, m, d = date_str.split("-")
    return f"{d}{sep}{m}{sep}{y}"


def _weekday(date_str: str) -> str:
    try:
        return _WEEKDAYS[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except ValueError:
        return ""


def _ascii(s: str) -> str:
    """Remove acentos p/ nome de pasta seguro entre SOs (zip Mac->Windows)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))


_META = ".meta"   # subpasta oculta no bundle: legenda+hashtags p/ reconstruir o index


def _order(cfg) -> list:
    slots = list(cfg["slots"].keys())
    return [s for s in _SLOT_ORDER if s in slots] + [s for s in slots if s not in _SLOT_ORDER]


def day_folder(date_str: str) -> str:
    return _fmt(date_str, "-")                        # 27-06-2026


def slot_name(cfg, slot: str, date_str: str) -> str:
    """Nome do arquivo de vídeo (sem extensão). O slot do dia da semana vira o nome do
    dia (ex.: 'sabado', 'quarta-feira') p/ ela se localizar; os demais usam o slot."""
    if cfg["slots"][slot].get("weekday"):
        return _ascii(_weekday(date_str)) or slot
    return slot


def video_dest(cfg, bundle: str, slot: str, date_str: str) -> str:
    """Caminho final do vídeo dentro do bundle: <bundle>/<dia>/<slot>.mp4."""
    return os.path.join(bundle, day_folder(date_str), f"{slot_name(cfg, slot, date_str)}.mp4")


def _meta_path(bundle: str, dayf: str, slotn: str) -> str:
    return os.path.join(bundle, _META, f"{dayf}_{slotn}.json")


def _ingest(cfg, bundle: str, dates: list):
    """Traz o que foi gerado no working oculto (output/.work) p/ dentro do bundle:
    vídeo -> <dia>/<slot>.mp4 e legenda+hashtags -> .meta/<dia>_<slot>.json. Idempotente
    (só o que falta/mudou). Deixa o bundle autossuficiente (sobrevive à limpeza do .work)."""
    os.makedirs(os.path.join(bundle, _META), exist_ok=True)
    for d in dates:
        dayf = day_folder(d)
        for slot in _order(cfg):
            wsrc = path("output", ".work", d, slot)
            wvid = os.path.join(wsrc, "video.mp4")
            if not os.path.exists(wvid):
                continue
            slotn = slot_name(cfg, slot, d)
            os.makedirs(os.path.join(bundle, dayf), exist_ok=True)
            vdst = os.path.join(bundle, dayf, f"{slotn}.mp4")
            if not (os.path.exists(vdst) and os.path.getsize(vdst) == os.path.getsize(wvid)):
                shutil.copy2(wvid, vdst)
            with open(_meta_path(bundle, dayf, slotn), "w", encoding="utf-8") as f:
                json.dump({"caption": _read(os.path.join(wsrc, "caption.txt")),
                           "hashtags": _read(os.path.join(wsrc, "hashtags.txt"))},
                          f, ensure_ascii=False)


def _collect(cfg, bundle: str, dates: list) -> list:
    """Lê o que JÁ está no bundle (vídeos + .meta). O bundle é a fonte de verdade."""
    items = []
    for d in dates:
        dayf = day_folder(d)
        for slot in _order(cfg):
            slotn = slot_name(cfg, slot, d)
            if not os.path.exists(os.path.join(bundle, dayf, f"{slotn}.mp4")):
                continue
            cap = tags = ""
            mp = _meta_path(bundle, dayf, slotn)
            if os.path.exists(mp):
                m = json.load(open(mp, encoding="utf-8"))
                cap, tags = m.get("caption", ""), m.get("hashtags", "")
            items.append({"date": d, "slot": slot, "dayf": dayf, "slotn": slotn,
                          "paste": (cap + "\n\n" + tags).strip(), "rel": f"{dayf}/{slotn}.mp4"})
    return items


def _card(it: dict) -> str:
    return f'''
      <div class="card">
        <div class="slot">{_SLOT_LABEL.get(it["slot"], it["slot"])}</div>
        <video src="{it["rel"]}" controls preload="metadata"></video>
        <div class="path">📁 {it["dayf"]}/{it["slotn"]}.mp4</div>
        <textarea readonly>{html.escape(it["paste"])}</textarea>
        <button onclick="cp(this)">Copiar legenda</button>
      </div>'''


def _html(items: list, title: str) -> str:
    blocks = []
    for d, grp in groupby(items, key=lambda x: x["date"]):
        cards = "".join(_card(it) for it in grp)
        blocks.append(f'''
    <section class="day">
      <h2>{_fmt(d)} <span>{_weekday(d)}</span></h2>
      <div class="row">{cards}</div>
    </section>''')
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>
:root{{--bg:#0f1115;--card:#1a1d24;--ink:#e7e7e7;--muted:#8a93a3;--accent:#2d6cdf;--line:#2a2e37}}
*{{box-sizing:border-box}}
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink);margin:0}}
header{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
  padding:16px 24px;z-index:5}}
header h1{{margin:0;font-size:17px;font-weight:700}}
header p{{margin:4px 0 0;color:var(--muted);font-size:13px}}
header > div{{max-width:1680px;margin:0 auto}}
.day{{padding:18px 24px;border-bottom:1px solid var(--line);max-width:1680px;margin:0 auto}}
.day h2{{margin:0 0 12px;font-size:15px;font-weight:700;text-transform:capitalize}}
.day h2 span{{color:var(--muted);font-weight:500;margin-left:8px;text-transform:none}}
.row{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:12px;display:flex;flex-direction:column;gap:9px}}
.slot{{font-weight:600;font-size:13px;color:#9ad}}
video{{width:100%;height:52vh;max-height:560px;min-height:340px;object-fit:contain;
  border-radius:10px;background:#000}}
.path{{font-size:11px;color:var(--muted);font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
textarea{{width:100%;height:96px;resize:none;overflow-y:auto;border:1px solid var(--line);
  border-radius:9px;padding:8px;font-size:12px;font-family:inherit;color:var(--ink);background:#0f1115}}
button{{background:var(--accent);color:#fff;border:0;border-radius:9px;padding:9px;font-size:13px;
  font-weight:600;cursor:pointer;transition:background .15s}}
button:hover{{filter:brightness(1.1)}}
button.ok{{background:#1e9e5a}}
</style></head><body>
<header><h1>{html.escape(title)}</h1><p>{len(items)} vídeos</p></header>
{"".join(blocks)}
<script>
function cp(b){{const t=b.closest('.card').querySelector('textarea');
navigator.clipboard.writeText(t.value);const o=b.textContent;
b.textContent='Copiado ✓';b.classList.add('ok');
setTimeout(()=>{{b.textContent=o;b.classList.remove('ok')}},1400);}}
</script></body></html>'''


def bundle_path(cfg, niche: str, dates: list) -> str:
    """Caminho da pasta de entrega do intervalo (estável — acumula os dias)."""
    disp = cfg.get("name", niche)
    d0, d1 = _fmt(dates[0], "-"), _fmt(dates[-1], "-")
    name = f"{disp} | {d0}" if dates[0] == dates[-1] else f"{disp} | {d0} - {d1}"
    return path("output", "_packages", name)


def cleanup_work():
    """Apaga o diretório de trabalho oculto. Chamar no fim da run — o bundle já é
    autossuficiente (vídeos + .meta), então nada de valor se perde."""
    shutil.rmtree(path("output", ".work"), ignore_errors=True)


def build_package(cfg, niche: str, dates: list, quiet: bool = False) -> str:
    """Atualiza o bundle: traz o que foi gerado (output/.work) p/ dentro dele e reescreve
    o index.html a partir do PRÓPRIO bundle. Idempotente; pode rodar a cada vídeo (ao vivo)."""
    bundle = bundle_path(cfg, niche, dates)
    os.makedirs(bundle, exist_ok=True)
    _ingest(cfg, bundle, dates)
    items = _collect(cfg, bundle, dates)
    disp = cfg.get("name", niche)
    title = f"{disp.capitalize()} · {_fmt(dates[0])}" + (
        "" if dates[0] == dates[-1] else f" → {_fmt(dates[-1])}")
    with open(os.path.join(bundle, "index.html"), "w", encoding="utf-8") as f:
        f.write(_html(items, title))
    if not quiet:
        print(f"  📂 pacote: {bundle}  ({len(items)} vídeos)")
        print(f"     revise: abra o index.html dessa pasta  ·  pra enviar: zipe a pasta")
    return bundle
