"""Pipeline de produção (orquestração). Gera 1 slot: versículo -> LLM -> eval ->
imagem/TTS/montagem -> pacote pronto. O CLI (factory/cli.py) chama isto."""
import json
import os
import random
import unicodedata
import uuid
from datetime import datetime, timezone

from . import content, evaluation, packaging
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


def run_slot(cfg, niche: str, slot: str, date_str: str, voice: dict = None, on_progress=None) -> dict:
    run_id = uuid.uuid4().hex[:12]
    ts = datetime.now(timezone.utc).isoformat()
    # diretório de trabalho OCULTO e temporário; build_package leva o resultado p/ o
    # bundle e cleanup_work() apaga isto no fim (output/ não fica com pastas de dia soltas).
    out_dir = path("output", ".work", date_str, slot)
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
                       {"variants": [], "chosen_idx": None, "verdict": "FAIL"}, hc, out_dir, None,
                       voice=voice, date_str=date_str)

    # 4. LLM-judge: pass@k -> escolhe a melhor frase
    jr = evaluation.judge(cfg, slot, verse, variants)
    chosen = jr.get("chosen_idx")
    print(f"  judge: {jr.get('verdict')} (chosen={chosen})")
    if jr.get("verdict") != "PASS" or chosen is None:
        return _record(cfg, niche, slot, run_id, ts, verse, variants, jr, hc, out_dir, None,
                       voice=voice, date_str=date_str)

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

    # 9. pacote pronto — só os artefatos necessários: video.mp4 + caption.txt + hashtags.txt
    hashtags = _compose_hashtags(cfg, slot, weekday)
    _write_package(out_dir, chosen_variant, hashtags)
    # limpa intermediários (não são artefatos): imagens + voz
    for p in [*imgs, voice_path]:
        if os.path.exists(p):
            os.remove(p)
    if on_progress:
        on_progress()   # atualiza a pasta de revisão ao vivo
    return _record(cfg, niche, slot, run_id, ts, verse, variants, jr, hc_video, out_dir, chosen,
                   voice=voice, date_str=date_str)


def _write_package(out_dir, variant, hashtags):
    """Grava só os artefatos que importam: caption.txt + hashtags.txt (video.mp4 já existe)."""
    with open(os.path.join(out_dir, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(variant["caption"])
    with open(os.path.join(out_dir, "hashtags.txt"), "w", encoding="utf-8") as f:
        f.write(" ".join(hashtags))


def _record(cfg, niche, slot, run_id, ts, verse, variants, jr, hc, out_dir, chosen,
            voice=None, date_str=None):
    ch = evaluation.content_hash(verse["ref"], variants[chosen]["frase"] if chosen is not None else "")
    # voz usada na locução, persistida no SQLite (metadata da run; NÃO é artefato).
    # Permite, no futuro, achar qual voz gerou um vídeo e podá-la do pool.
    voice_tag = f"{voice['name']} ({voice['id']})" if isinstance(voice, dict) else None
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
        "voice": voice_tag,
        "date": date_str,
    }
    store.record_eval(row)
    # Só marca versículo como usado se o pacote foi de fato produzido (PASS).
    if chosen is not None and jr.get("verdict") == "PASS":
        store.mark_used(verse["ref"], run_id, ts)
    return {"run_id": run_id, "verdict": jr.get("verdict"), "out_dir": out_dir}


def run_batch(cfg, niche: str, date_str: str, bundle: str, only_slot: str = None,
              force: bool = False, on_progress=None) -> list:
    """Roda os slots de UM dia, com vozes distintas. Idempotente: pula slots cujo vídeo
    já está NO BUNDLE (a não ser force=True). Retorna [{slot, status}] (ok|fail|skip)."""
    store.init()
    slots = [only_slot] if only_slot else list(cfg["slots"].keys())
    out, todo = [], []
    for slot in slots:
        if not force and os.path.exists(packaging.video_dest(cfg, bundle, slot, date_str)):
            out.append({"slot": slot, "status": "skip"})
        else:
            todo.append(slot)
    pool = cfg["tts"]["voices"]
    voice_map = (dict(zip(todo, random.sample(pool, len(todo))))
                 if len(todo) > 1 and len(pool) >= len(todo) else {})
    for slot in todo:
        try:
            res = run_slot(cfg, niche, slot, date_str, voice=voice_map.get(slot), on_progress=on_progress)
            out.append({"slot": slot, "status": "ok" if res.get("verdict") == "PASS" else "fail"})
        except Exception as e:  # noqa: BLE001 — loga e segue p/ próximo slot
            print(f"  ERRO em {slot}: {e}")
            out.append({"slot": slot, "status": "fail"})
    return out


def run_range(cfg, niche: str, dates: list, only_slot: str = None, force: bool = False) -> dict:
    """Gera vários dias em sequência (idempotente). Imprime progresso + resumo final."""
    store.init()
    bundle = packaging.bundle_path(cfg, niche, dates)
    print(f"📂 Acompanhe AO VIVO (atualize o navegador): {os.path.join(bundle, 'index.html')}\n")
    on_progress = lambda: packaging.build_package(cfg, niche, dates, quiet=True)  # noqa: E731
    on_progress()   # cria a pasta/html já no começo (mesmo vazio fica pronto pra abrir)
    tot = {"ok": 0, "fail": 0, "skip": 0}
    for d in dates:
        print(f"\n########## {d} ##########")
        for r in run_batch(cfg, niche, d, bundle, only_slot=only_slot, force=force, on_progress=on_progress):
            tot[r["status"]] = tot.get(r["status"], 0) + 1
            if r["status"] == "skip":
                print(f"  (pula {r['slot']} — já existe)")
    print(f"\n===== RESUMO: {tot['ok']} gerados · {tot['skip']} pulados · {tot['fail']} falhas "
          f"· {len(dates)} dia(s) =====")
    packaging.build_package(cfg, niche, dates)   # rebuild final (com print do caminho)
    packaging.cleanup_work()   # apaga o working oculto; bundle já é autossuficiente
    return tot
