"""Adapter de imagem de fundo (licença livre): Pexels (se houver chave) ou
Openverse CC0 (sem chave). ffmpeg recorta p/ vertical depois."""
from __future__ import annotations

import os
import random

import requests

from ..config import env

UA = {"User-Agent": "pro-cult/1.0"}


def _download(url: str, out_path: str) -> str:
    img = requests.get(url, headers=UA, timeout=60)
    img.raise_for_status()
    if "image" not in img.headers.get("Content-Type", ""):
        raise RuntimeError(f"URL não é imagem: {url}")
    with open(out_path, "wb") as f:
        f.write(img.content)
    return out_path


def _pexels_urls(query: str, count: int, key: str) -> list:
    r = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": key},
        params={"query": query, "orientation": "portrait",
                "per_page": max(15, count * 3), "size": "large"},
        timeout=30,
    )
    r.raise_for_status()
    photos = r.json().get("photos", [])
    random.shuffle(photos)
    return [p["src"]["large2x"] for p in photos]


def _openverse_urls(query: str, count: int) -> list:
    r = requests.get(
        "https://api.openverse.org/v1/images/",
        params={"q": query, "license": "cc0,pdm", "page_size": 30, "mature": "false"},
        headers=UA, timeout=30,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    random.shuffle(results)
    return [it["url"] for it in results if it.get("url")]


def _image_urls(query: str, count: int) -> list:
    key = env("PEXELS_API_KEY")
    return _pexels_urls(query, count, key) if key else _openverse_urls(query, count)


def fetch_images(query: str, n: int, out_dir: str, prefix: str = "bg") -> list:
    """Baixa n imagens DISTINTAS (Pexels se houver chave; senão Openverse CC0).
    Se vier menos que n, repete a última pra completar."""
    urls = _image_urls(query, n)
    paths = []
    for u in urls:
        if len(paths) >= n:
            break
        try:
            paths.append(_download(u, os.path.join(out_dir, f"{prefix}{len(paths)}.jpg")))
        except (requests.RequestException, RuntimeError):
            continue
    if not paths:
        raise RuntimeError(f"Nenhuma imagem usável para: {query}")
    while len(paths) < n:
        paths.append(paths[-1])
    return paths


def fetch_image(query: str, out_path: str) -> str:
    """Conveniência: 1 imagem (mantida p/ compat)."""
    d, base = os.path.dirname(out_path), os.path.basename(out_path)
    return fetch_images(query, 1, d or ".", prefix=base.rsplit(".", 1)[0])[0]
