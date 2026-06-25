"""Adapter de LLM via Claude Code headless — usa a SUBSCRIPTION, não a API paga.

`claude -p --output-format json` roda com a auth do Claude Code:
  - local: usa seu login da assinatura (Pro/Max) automaticamente;
  - cron/cloud: exporte CLAUDE_CODE_OAUTH_TOKEN (gere com `claude setup-token`, dura 1 ano).

IMPORTANTE: se ANTHROPIC_API_KEY estiver setado, o Claude Code usa a API PAGA.
Por isso removemos essa env do fluxo (e a tiramos do subprocess por segurança).
"""
from __future__ import annotations

import json
import os
import subprocess


def complete(prompt: str, model: str | None = None, timeout: int = 180) -> str:
    """Roda o prompt e devolve o texto final da resposta."""
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    # Garante subscription: nunca passar ANTHROPIC_API_KEY adiante.
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"`claude -p` falhou (rc={proc.returncode}): {proc.stderr.strip()}")
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout.strip()
    if isinstance(envelope, dict):
        if envelope.get("is_error"):
            raise RuntimeError(f"`claude -p` erro: {envelope.get('result')}")
        return envelope.get("result", "")
    return proc.stdout.strip()


def _extract_json(text: str):
    """Parseia JSON tolerando cercas ```json e texto em volta."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
            text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        i, j = text.find("{"), text.rfind("}")   # fallback: do 1º { ao último }
        if i != -1 and j > i:
            return json.loads(text[i:j + 1])
        raise


def complete_json(prompt: str, model: str | None = None, retries: int = 3) -> dict:
    """complete() + parse de JSON, com re-tentativa (LLM às vezes devolve vazio/texto)."""
    last = "(sem detalhe)"
    for _ in range(retries):
        text = complete(prompt, model=model)
        if not text.strip():
            last = "resposta vazia"
            continue
        try:
            return _extract_json(text)
        except (json.JSONDecodeError, ValueError) as e:
            last = f"{type(e).__name__}: {text[:150]}"
            continue
    raise RuntimeError(f"complete_json falhou após {retries} tentativas — {last}")
