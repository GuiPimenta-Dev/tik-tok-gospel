# Pro-Cult — Fábrica de Shorts

Fábrica automatizada de shorts faceless (PT-BR). v1: canal TikTok de
**bom dia / boa tarde / boa noite** (saudação + versículo + frase motivacional).

> Design completo e princípios invioláveis em [`CLAUDE.md`](./CLAUDE.md).

## Setup (Fase 0)

```bash
# 1. dependências
brew install ffmpeg                 # ffmpeg + ffprobe (binários do sistema)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. chaves
cp .env.example .env                # preencha PEXELS_API_KEY
#   - LLM usa sua SUBSCRIPTION via `claude -p` (NÃO setar ANTHROPIC_API_KEY).
#   - ELEVENLABS_API_KEY já está exportado no ambiente.

# 3. dataset bíblico (domínio público)
python scripts/fetch_bible.py       # -> data/bible/almeida.json

# 4. assets
#   - assets/fonts/font.ttf   (fonte grande/legível; defina o caminho em config/bom-dia.yaml)
#   - assets/music/*.mp3       (instrumentais ROYALTY-FREE; rotacionados)
python -m factory.cli voices --niche bom-dia   # amostras do pool de vozes
```

## Rodar (Fase 1 — na mão)

```bash
python -m factory.cli pipeline --niche bom-dia --date today    # gera os 4 slots
python -m factory.cli pipeline --niche bom-dia --slot manha    # gera 1 slot
```

Saída: `output/AAAA-MM-DD/<slot>/` com `video.mp4`, `caption.txt`, `hashtags.txt`, `meta.json`.
Você revisa e sobe no **agendador do TikTok** (upload manual = inviolável).

## Eval

Cada run grava uma linha em `data/evals.sqlite`. Na fase copiloto, registre seu
veredito humano e compare com o do judge:

```bash
# taxa de concordância judge <-> humano por versão de rubric
sqlite3 data/evals.sqlite "SELECT rubric_version,
  AVG(judge_verdict = human_verdict) AS concordancia, COUNT(*) n
  FROM evals WHERE human_verdict IS NOT NULL GROUP BY rubric_version;"
```

Gate vira autônomo só quando a concordância estabilizar alta (>90%). Veja
`CLAUDE.md` §6–7.
