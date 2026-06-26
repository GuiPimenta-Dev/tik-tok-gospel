"""Conteúdo: versículo (verbatim do dataset) + frase motivacional (LLM).

PRINCÍPIO INVIOLÁVEL: o texto do versículo NUNCA é gerado pelo LLM. É resolvido
verbatim do dataset Almeida. O LLM só seleciona tom e escreve a moldura.
"""
import json
import random
import unicodedata

from ..adapters import llm, store
from ..config import path


def _norm(s: str) -> str:
    """Normaliza nome de livro: minúsculo, sem acento, só alfanumérico.
    Ex.: '1 João' -> '1joao', 'Êxodo' -> 'exodo'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def _load_dataset(cfg) -> dict:
    """Indexa o dataset por nome normalizado E abbrev -> lista de capítulos."""
    with open(path(cfg["bible"]["dataset"]), encoding="utf-8") as f:
        books = json.load(f)
    idx = {}
    for b in books:
        idx[_norm(b.get("name", ""))] = b["chapters"]
        idx[_norm(b.get("abbrev", ""))] = b["chapters"]
    return idx


def _verse_text(dataset: dict, book: str, chapter: int, verse: int) -> str:
    chapters = dataset.get(_norm(book))
    if chapters is None:
        raise KeyError(f"Livro não encontrado no dataset: {book}")
    return chapters[chapter - 1][verse - 1].strip()


def select_unused_verse(cfg, slot: str) -> dict:
    """Escolhe um versículo do pool, com afinidade ao slot, ainda não usado.
    Retorna {ref, book, chapter, verse, text}."""
    dataset = _load_dataset(cfg)
    with open(path(cfg["bible"]["pool"]), encoding="utf-8") as f:
        pool = json.load(f)["verses"]

    def fits(v):
        slots = v.get("slots")
        return (not slots) or (slot in slots)

    reuse = cfg["bible"].get("reuse_after_days")
    candidates = [v for v in pool if fits(v)]
    random.shuffle(candidates)
    # 1ª passada: não-usados com afinidade ao slot. Fallback: qualquer não-usado.
    for bucket in (candidates, [v for v in pool if v not in candidates]):
        for v in bucket:
            ref = f"{v['book']} {v['chapter']}:{v['verse']}"
            if not store.is_used(ref, reuse):
                return {
                    "ref": ref, "book": v["book"], "chapter": v["chapter"],
                    "verse": v["verse"], "text": _verse_text(dataset, v["book"], v["chapter"], v["verse"]),
                }
    raise RuntimeError("Pool esgotado — todos os versículos já foram usados. Expanda o pool.")


def generate_frames(cfg, slot: str, verse: dict, k: int, greeting: str) -> list:
    """LLM call #1: gera k variações de {gancho, frase, cta, caption}.
    NÃO reescreve o versículo. `greeting` é a saudação efetiva (ex: "Bom dia" ou
    "Feliz quinta-feira" no slot do dia da semana)."""
    slot_cfg = cfg["slots"][slot]

    prompt = f"""Você cria conteúdo para um canal de TikTok de mensagens cristãs \
("{greeting}"), para um público brasileiro 50+, religioso.

Saudação: {greeting}
Tom desejado: {slot_cfg['tone']}
Versículo (NÃO reescreva, NÃO parafraseie — ele será exibido verbatim):
  "{verse['text']}" — {verse['ref']}

Gere {k} variações DIFERENTES. Cada variação tem 5 campos:
- "gancho": a PRIMEIRA frase que aparece na tela (2s iniciais), feita pra fazer a \
  pessoa PARAR de rolar. Curtíssima (3 a 8 palavras), de endereçamento direto e \
  acolhedor — faz a pessoa sentir que a mensagem é PRA ELA. Ex.: "Deus tem um recado \
  pra você", "Essa mensagem chegou no momento certo", "Respira: você não está só". \
  REGRA DE OURO: acolhimento e relevância, NUNCA barganha/medo/promessa \
  ("compartilhe ou perde a bênção", "assista até o fim pra receber" = PROIBIDO).
- "frase": frase motivacional curta (1 a 2 frases) que conversa com o versículo.
- "cta": chamada final curta e gentil de engajamento. Ex.: "Marque alguém que \
  precisa ler isso hoje", "Comente um Amém 🙏". Sem barganha/medo.
- "caption": legenda curta e acolhedora para o post (sem hashtags — elas são curadas à parte).

LINGUAGEM (muito importante): escreva como mensagem carinhosa no WhatsApp da \
família — palavras simples do dia a dia, que sua avó entenderia sem dicionário. \
Frases curtas. Meio-termo: simples, mas com um toque inspirador. Ex. de reescrita: \
"Que a serenidade preencha o seu coração" -> "Que o seu coração fique em paz".

Regras: PT-BR correto; sem promessa de cura/dinheiro; sem teologia polêmica; sem \
política/medo/culpa. Nada (gancho/frase/cta) deve repetir o texto do versículo nem \
conter a saudação "{greeting}" (ela é falada à parte).

Responda APENAS com JSON válido:
{{"variants": [{{"gancho": "...", "frase": "...", "cta": "...", "caption": "..."}}]}}"""

    return llm.complete_json(prompt)["variants"][:k]
