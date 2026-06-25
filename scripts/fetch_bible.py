"""Baixa a Bíblia Almeida (ACF, domínio público) e salva em data/bible/almeida.json.

Fonte: github.com/thiagobodruk/bible (JSON livre, domínio público).
Formato salvo: lista de livros [{"abbrev","name","chapters":[[verso,...],...]}].
Uso: python scripts/fetch_bible.py
"""
import json
import os
import sys
import urllib.request

URL = "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/pt_acf.json"
# scripts/ -> raiz do projeto -> data/bible/almeida.json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "bible", "almeida.json")


def main():
    print(f"Baixando {URL} ...")
    req = urllib.request.Request(URL, headers={"User-Agent": "pro-cult/1.0"})
    raw = urllib.request.urlopen(req, timeout=60).read()

    # O dataset historicamente vem em utf-8-sig (com BOM) ou latin-1. Tenta ambos.
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            data = json.loads(raw.decode(enc))
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = None
    if data is None:
        sys.exit("Falhou ao decodificar o dataset.")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"OK: {len(data)} livros salvos em {OUT}")


if __name__ == "__main__":
    main()
