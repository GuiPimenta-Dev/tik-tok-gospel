"""Eval: hard checks (determinísticos) + LLM-judge (rubric versionado) + golden.

Hard checks rodam ANTES do judge (baratos primeiro). O judge faz pass@k sobre as
variações. Na v1 o gate é COPILOTO: classifica e explica, não bloqueia.
"""
from __future__ import annotations

import glob
import hashlib
import json
import subprocess

from . import content
from ..adapters import llm
from ..config import path


def rubric_version(cfg) -> str:
    """Hash curto do rubric — carimba cada eval p/ rastrear regressão."""
    with open(path(cfg["eval"]["rubric"]), "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:10]


def content_hash(verse_ref: str, frase: str) -> str:
    return hashlib.sha1(f"{verse_ref}|{frase}".encode()).hexdigest()[:16]


def hard_checks(cfg, slot: str, verse: dict, video_path: str | None = None) -> dict:
    """Checks objetivos. Retorna {check: bool, ...} + 'pass'."""
    checks = {}
    # 1) versículo bate verbatim com o dataset
    try:
        dataset = content._load_dataset(cfg)
        truth = content._verse_text(dataset, verse["book"], verse["chapter"], verse["verse"])
        checks["verse_verbatim"] = truth == verse["text"]
        checks["verse_ref_exists"] = True
    except (KeyError, IndexError):
        checks["verse_verbatim"] = False
        checks["verse_ref_exists"] = False

    # 2) formato do vídeo (só se já existir)
    if video_path:
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "stream=width,height,codec_type:format=duration",
                 "-of", "json", video_path],
                capture_output=True, text=True, check=True,
            )
            info = json.loads(probe.stdout)
            streams = info.get("streams", [])
            vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
            dur = float(info.get("format", {}).get("duration", 0))
            checks["resolution_ok"] = (vstream.get("width") == cfg["video"]["width"]
                                       and vstream.get("height") == cfg["video"]["height"])
            checks["has_audio"] = any(s.get("codec_type") == "audio" for s in streams)
            checks["duration_ok"] = cfg["video"]["min_seconds"] <= dur <= cfg["video"]["max_seconds"]
        except (subprocess.CalledProcessError, ValueError, json.JSONDecodeError):
            checks["resolution_ok"] = checks["has_audio"] = checks["duration_ok"] = False

    checks["pass"] = all(v for k, v in checks.items() if k != "pass")
    return checks


def judge(cfg, slot: str, verse: dict, variants: list) -> dict:
    """LLM-judge: pontua as variações contra o rubric. pass@k -> escolhe a melhor."""
    with open(path(cfg["eval"]["rubric"]), encoding="utf-8") as f:
        rubric = f.read()

    variants_txt = "\n".join(
        f"[{i}] gancho: {v.get('gancho', '')!r} | frase: {v.get('frase', '')!r} "
        f"| cta: {v.get('cta', '')!r}" for i, v in enumerate(variants))
    prompt = f"""Você é um avaliador rigoroso. Aplique o rubric abaixo às variações de \
frase motivacional para um vídeo de "{cfg['slots'][slot]['greeting']}" (tom: \
{cfg['slots'][slot]['tone']}), atrelado ao versículo:
  "{verse['text']}" — {verse['ref']}

=== RUBRIC ===
{rubric}
=== FIM RUBRIC ===

Variações:
{variants_txt}

Responda APENAS com o JSON no formato de saída especificado no rubric."""

    return llm.complete_json(prompt)


def run_golden(cfg) -> bool:
    """Regressão do judge: roda cada fixture do golden set e compara o veredito
    por-variante (pass) com o esperado. Rode sempre que mudar rubric/prompt."""
    files = sorted(glob.glob(path("rubric", "golden", "*.json")))
    if not files:
        print("(golden set vazio — adicione fixtures em rubric/golden/)")
        return True
    print(f"Golden set: {len(files)} fixture(s) | rubric {rubric_version(cfg)}\n")
    total = correct = 0
    mismatches = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            ex = json.load(f)
        variants = [{"gancho": c.get("gancho", ""), "frase": c.get("frase", ""),
                     "cta": c.get("cta", "")} for c in ex["cases"]]
        jr = judge(cfg, ex["slot"], ex["verse"], variants)
        by_idx = {v["idx"]: v for v in jr.get("variants", [])}
        for i, c in enumerate(ex["cases"]):
            got = bool(by_idx.get(i, {}).get("pass"))
            exp = bool(c["expected_pass"])
            total += 1
            if got == exp:
                correct += 1
            else:
                mismatches.append((fp.split("/")[-1], i, exp, got, c["frase"][:60]))
    print(f"Acurácia: {correct}/{total} = {correct / total:.0%}")
    for fn, i, exp, got, frase in mismatches:
        print(f"  ✗ {fn}[{i}] esperado={exp} obteve={got}: {frase}...")
    return not mismatches
