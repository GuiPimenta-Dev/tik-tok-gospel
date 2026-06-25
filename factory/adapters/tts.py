"""Adapter de voz (TTS) via REST do ElevenLabs (sem SDK) + seleção de voz do pool."""
from __future__ import annotations

import random

import requests

from ..config import env


def pick_voice(cfg) -> dict:
    """Sorteia uma voz do pool (rotação p/ não ficar monótono)."""
    return random.choice(cfg["tts"]["voices"])


def tts(text: str, out_path: str, cfg, voice_id: str) -> str:
    """Gera narração via REST do ElevenLabs (sem SDK). Tom sereno fixo p/ todas as vozes.

    Usa ELEVENLABS_API_KEY do ambiente (já exportado).
    """
    key = env("ELEVENLABS_API_KEY", required=True)
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": cfg["tts"]["model"],
            "language_code": "pt",
            "voice_settings": cfg["tts"]["settings"],
        },
        timeout=120,
    )
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path
