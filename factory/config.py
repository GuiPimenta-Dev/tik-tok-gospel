"""Carga de config (YAML do nicho) + env (.env) + paths do projeto."""
import os

import yaml

# factory/config.py -> raiz do projeto (2x dirname)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# python-dotenv é opcional: se ausente, usamos só env vars já exportadas.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass


def path(*parts):
    """Caminho absoluto a partir da raiz do projeto."""
    return os.path.join(ROOT, *parts)


def load_config(niche: str) -> dict:
    with open(path("config", f"{niche}.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def env(key: str, default=None, required=False) -> str:
    val = os.getenv(key, default)
    if required and not val:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {key}")
    return val
