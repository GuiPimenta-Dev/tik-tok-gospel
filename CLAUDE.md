# Pro-Cult — Fábrica de Shorts (spec de build & operação)

> Este arquivo é a fonte de verdade da fábrica. O agente (Claude Code) deve
> seguir estas decisões à risca. Elas foram travadas numa sessão de design e
> NÃO devem ser reinterpretadas sem o dono pedir.

---

## 1. Objetivo & escopo (v1)

Fábrica de vídeos curtos (**short-form, faceless, PT-BR**) totalmente automatizada
na **geração**, com **upload manual**. A v1 tem **um único nicho**:

**Canal TikTok cristão** — **4 shorts/dia**: manhã, tarde, noite (sem mencionar o
dia da semana) + **1 dedicado ao dia da semana** ("Feliz quinta-feira"). Cada vídeo:
**gancho** (prende em ~3.5s) → **saudação + versículo bíblico + frase motivacional**
→ **CTA**, sobre fotos com crossfade, voz serena e música suave.

- **Público:** 50+, religioso, brasileiro.
- **Meta desta fase:** *montar e estabilizar a fábrica* — não faturar ainda.
- **Multi-nicho:** a arquitetura é desenhada para múltiplos nichos (config-driven),
  mas a v1 **opera apenas um**. Nichos novos = nova config, mesmo pipeline.

---

## 2. Princípios invioláveis (não negociar sem o dono)

1. **Versículo nunca é gerado por LLM.** Vem *verbatim* de dataset de domínio
   público (Almeida ACF/ARC). O eval valida string exata + referência existente.
   Alucinar versículo destrói a credibilidade com este público.
2. **Áudio 100% royalty-free.** Música e SFX só de bibliotecas livres. Nada com
   copyright/Content ID — protege as contas e permite cross-post pro YT Shorts.
3. **Upload é manual.** Geração é automática; publicação passa por humano
   (agendador nativo do TikTok). Protege as contas contra ban por automação.
4. **Qualidade > automação.** "100% sem humano" não é meta. O gate de qualidade
   existe justamente para não publicar slop. Conteúdo ruim floppa, com ou sem IA.
5. **O eval é copiloto até provar concordância.** O LLM-judge só vira gate
   autônomo (bloqueando sozinho) depois de bater com o veredito humano de forma
   consistente (~>90% por 1–2 semanas). Antes disso ele só *classifica e explica*.
6. **Motor B (assembly), não generativo.** Vídeo é montado (imagem + TTS +
   legenda + ffmpeg), não gerado por IA. Generativo (Seedance etc.) está fora.
7. **Identidade consistente = marca.** O **tom sereno/calmo** (aplicado a todas as
   vozes), a assinatura visual e o handle são a marca. As vozes ROTACIONAM (pool)
   p/ não ficar monótono, mas o tom nunca muda. É o que separa "canal" de "spam".

---

## 3. Stack & arquitetura

- **Linguagem:** Python.
- **LLM = SUBSCRIPTION, não API paga.** Os *dois únicos* pontos de LLM —
  (a) frase motivacional + caption; (b) LLM-judge — chamam o Claude Code headless
  (`claude -p --output-format json`, via `src/llm.py`), que roda na assinatura
  Pro/Max. **NÃO usar o SDK `anthropic` nem setar `ANTHROPIC_API_KEY`** (isso
  ativaria cobrança de API). Cron/cloud: `claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN`.
  Decisão de v1: cortar custo ao máximo até validar que vale investir.
- **Vídeo/áudio:** `ffmpeg` — **N fotos (`video.images`) com crossfade (`xfade`) +
  Ken Burns (`zoompan`)**, `overlay`, mix voz/música. `ffprobe` (validação).
  **Texto renderizado com Pillow** (PNG transparente via `overlay`) — o ffmpeg local
  não tem `drawtext` (sem libfreetype), e o PNG dá tipografia/quebra/contorno melhores.
  **Legibilidade** via `overlay` no config: `scrim` (escurecimento de tela cheia,
  escalonado por slot) + `gradient` (halo suave atrás do texto).
- **Gancho + beats de texto:** cada vídeo abre com um **gancho** (LLM, prende em ~3.5s,
  endereçamento direto sem barganha) → **versículo** (referência separada por 2 linhas
  em branco = destaque) → **CTA** na cauda. Texto em beats cronometrados com fade.
- **Dia da semana:** só no slot `semana` (`weekday: true`), falado + na tela ("Feliz
  quinta-feira"); os outros 3 slots NÃO mencionam o dia. Derivado da `--date`.
  **Linguagem simples** (alvo "WhatsApp da família") forçada no prompt + rubric.
- **TTS:** ElevenLabs via **REST (requests, sem SDK)**. **Pool de ~10 vozes masculinas
  calmas/serenas** (femininas removidas: artificiais) em tom sereno fixo; o batch
  sorteia **vozes distintas por dia**. Voz registrada no `meta.json`.
- **Música:** pool royalty-free em `assets/music/` (rotação, entra no miolo p/ não ter
  intro fraca, mix **-20dB** + ducking; **voz -3dB**). `music.enabled`. Registrada no `meta.json`.
- **Hashtags (só na legenda, nunca na tela):** **5 curadas** (tag do tipo +
  1 ampla + nicho sorteado), pesquisa 2026. Vão em `hashtags.txt` separado.
- **Imagem:** Pexels API se houver `PEXELS_API_KEY`; senão **Openverse CC0 (sem chave)**.
- **Bíblia:** dataset Almeida (domínio público) local + ledger de usados.
- **Store de eval:** SQLite (1 arquivo, queryável, faz JOIN com métricas na Fase 2).

> **Não é um enxame de agentes.** O runtime é um **pipeline determinístico** com
> 2 chamadas de LLM. "Agentes de storytelling" só fazem sentido em nichos
> narrativos futuros — não neste.

---

## 4. Estrutura de pastas

```
pro-cult/
├── CLAUDE.md                  # este arquivo
├── .env                       # chaves (NUNCA versionar)
├── config/
│   └── bom-dia.yaml           # config do nicho (1 arquivo por nicho)
├── data/
│   ├── bible/almeida.json     # dataset domínio público
│   ├── used_verses.sqlite     # ledger de versículos usados
│   └── evals.sqlite           # store de eval + métricas (Fase 2)
├── assets/
│   ├── music/                 # instrumentais royalty-free (rotacionar)
│   └── fonts/                 # fonte grande/legível p/ overlay
├── rubric/
│   ├── bom-dia.md             # rubric do judge (VERSIONADO no git)
│   └── golden/                # golden set p/ regressão do judge
├── scripts/fetch_bible.py    # baixa o dataset Almeida
├── output/
│   └── AAAA-MM-DD/            # 4 slots/dia: manha, tarde, noite, semana
│       └── <slot>/  → video.mp4 + caption.txt + hashtags.txt + meta.json
│                       (+ bg0/1/2.jpg, voice.mp3 intermediários)
├── factory/                  # pacote (camadas: cli -> domain -> adapters -> config)
│   ├── config.py             # paths + env + load_config
│   ├── cli.py                # entrypoint: pipeline | voices | golden | label
│   ├── domain/               # regras + orquestração (sem I/O externo direto)
│   │   ├── content.py        # versículo (dataset) + LLM (gancho/frase/cta/caption)
│   │   ├── evaluation.py     # hard checks + LLM-judge + golden
│   │   └── pipeline.py       # run_slot / run_batch + hashtags/weekday/beats
│   └── adapters/             # integrações externas
│       ├── llm.py            # claude -p (subscription) com retry/JSON
│       ├── tts.py            # ElevenLabs REST + pick_voice
│       ├── images.py         # Pexels / Openverse CC0
│       ├── video.py          # ffmpeg + Pillow (scrim/texto/beats) + pick_music
│       └── store.py          # SQLite (evals, metrics, used_verses)
└── logs/
```

**Camadas:** `cli` → `domain` → `adapters` → `config`. Domínio importa adapters direto
(layered enxuto, sem Protocols); adapters não importam domínio.

> Versão *enxuta* da estrutura do workflow de referência. SEM `/remotion`,
> `/clips/act-X` etc. — não se aplicam ao Motor B deste nicho.

---

## 5. Pipeline de produção (ordem importa — falha cedo = barato)

São **4 slots/dia**: `manha`, `tarde`, `noite` (sem dia da semana) + `semana` (dia da
semana). O batch sorteia **4 vozes distintas** do pool. Para cada slot:

1. **Seleciona versículo** não-usado do dataset Almeida (consulta o ledger).
2. **Saudação efetiva:** slot `semana` → "Feliz <dia>"; demais → saudação fixa (sem dia).
3. **LLM call #1:** gera **k=3 variações** de **gancho + frase + cta + caption**
   (sem hashtags — curadas à parte; linguagem simples; não repete saudação/versículo).
4. **Hard checks:** versículo bate string exata + existe; não está no ledger;
   formato do vídeo 1080×1920, áudio, duração 12–30s (`ffprobe`).
5. **LLM-judge (call #2):** pontua as k variações contra `rubric/bom-dia.md` (gancho
   sem barganha, coerência, tom, PT-BR simples, brand-safe). `pass@k` escolhe a melhor.
6. **Imagem:** N fotos (`video.images`) — Pexels (se chave) ou Openverse CC0.
7. **ElevenLabs TTS:** voz do dia narra **gancho → saudação → frase → versículo**.
8. **ffmpeg:** N fotos com crossfade + zoom → scrim constante → **3 beats de texto**
   (gancho / versículo / CTA) com fade → mix voz(-3dB)+música(-20dB, entra no miolo) →
   **cauda ≥4s com fade-out**, **teto 30s**. → `video.mp4` 1080×1920.
9. **Grava o pacote:** `video.mp4` + `caption.txt` (legenda) + `hashtags.txt`
   (5 hashtags: tag do tipo + 1 ampla + nicho) + `meta.json`.
10. **Registra a run no store de eval** (ver §7).
11. **Humano revisa** e sobe no **agendador do TikTok** (4 de uma vez).

Execução v1: **rodar na mão** (`python -m src.pipeline --niche bom-dia --date today`),
ver cada vídeo sair. Depois → `launchd` agendado → cloud (GitHub Actions cron).

---

## 6. Eval & quality gate

Duas zonas:

- **Hard checks (determinísticos, baratos, rodam primeiro):** versículo verbatim,
  ledger, formato/duração, integridade do arquivo.
- **LLM-judge (rubric versionado):** coerência versículo↔frase, tom do horário,
  PT-BR correto, brand-safety. `pass@k` com **k=3**: gera 3 frases, judge escolhe
  a melhor que passa; se nenhuma passa, reprova o slot.

**Progressão do gate (princípio nº5):**
- **Fase copiloto (v1):** judge **classifica e explica** (PASS/FAIL + motivo) e
  grava o veredito; o **humano decide** e também grava o seu veredito.
- **Promoção:** quando a **concordância judge↔humano** estabilizar alta (>90% por
  ~1–2 semanas), liga o **gate autônomo** + auto-retry (N tentativas, depois alerta).

O `rubric/bom-dia.md` é versionado no git e é o ponto onde, na Fase 2, entram os
aprendizados das métricas reais.

---

## 7. Infra de eval (SQLite, SQL na mão primeiro; dashboard depois)

Toda run grava uma linha **imutável**. Carimba sempre `rubric_version`,
`prompt_version`, `model_id` p/ rastreabilidade e regressão.

```sql
CREATE TABLE evals (
  run_id          TEXT PRIMARY KEY,
  ts              TEXT NOT NULL,
  niche           TEXT NOT NULL,
  slot            TEXT NOT NULL,           -- manha|tarde|noite
  verse_ref       TEXT NOT NULL,
  verse_text      TEXT NOT NULL,
  frame_variants  TEXT NOT NULL,           -- JSON: as k frases geradas
  judge_scores    TEXT NOT NULL,           -- JSON: score por variante
  chosen_idx      INTEGER,
  hard_checks     TEXT NOT NULL,           -- JSON: {verbatim:true, format:..}
  judge_verdict   TEXT NOT NULL,           -- PASS|FAIL
  judge_reasons   TEXT,
  human_verdict   TEXT,                    -- PASS|FAIL (fase copiloto)
  prompt_version  TEXT NOT NULL,
  rubric_version  TEXT NOT NULL,           -- hash/tag do rubric.md
  model_id        TEXT NOT NULL,
  content_hash    TEXT NOT NULL            -- chave de join c/ metrics
);

-- Preenchida na Fase 2 (loop de feedback c/ métricas reais do TikTok)
CREATE TABLE metrics (
  content_hash    TEXT PRIMARY KEY,
  run_id          TEXT REFERENCES evals(run_id),
  views           INTEGER,
  completion_rate REAL,
  watch_time_s    REAL,
  shares          INTEGER,
  pulled_at       TEXT
);
```

- **Golden set** (`rubric/golden/`): ~10–20 exemplos rotulados (bons e ruins),
  crescendo a partir dos labels humanos. Roda como **suite de regressão** sempre
  que o rubric/prompt mudar — garante que uma mudança não passou a aprovar lixo
  nem reprovar bom.
- **Métrica-chave da v1:** *taxa de concordância judge↔humano por versão de rubric*
  (`SELECT` simples sobre `evals`). É o gatilho objetivo da promoção do gate.
- **Dashboard:** só depois, quando houver dados suficientes. Por ora, SQL na mão.

---

## 8. Roadmap por fase

| Fase | Entrega |
|---|---|
| **0 — Setup** | `.env` (Pexels), dataset Almeida, pool de vozes auditado, fonte, ~5–10 instrumentais |
| **1 — Pipeline** | Pipeline ponta-a-ponta rodando na mão; 1 pacote pronto por slot; store de eval gravando; rubric v1 + golden set inicial |
| **2 — Calibração** | Rodar diário, comparar judge↔humano, evoluir rubric, medir concordância |
| **3 — Promoção** | Gate autônomo + auto-retry; `launchd` agendado |
| **4 — Loop de feedback** | Ingestão de métricas reais do TikTok → tabela `metrics`; correlacionar score×performance; few-shots de ganchos vencedores |
| **5 — Escala** | Cloud (GH Actions cron); descobrir nicho #2 (reativa YouTube Data API + agente de pesquisa data-driven, decisão final humana) |

---

## 9. Setup & env

```bash
# .env (NUNCA versionar)
PEXELS_API_KEY=...
# Vozes: pool em config/<niche>.yaml (rotação, tom sereno). Amostras: python -m src.voices
# ELEVENLABS_API_KEY: já exportado no ambiente (chave só-TTS, sem permissão de listar vozes).
# LLM: subscription (NÃO setar ANTHROPIC_API_KEY). Cron: CLAUDE_CODE_OAUTH_TOKEN.
```

- Dataset Almeida: baixar JSON de domínio público para `data/bible/almeida.json`.
- **Custo estimado v1: praticamente só ElevenLabs (poucos dólares/mês).** LLM = $0
  (assinatura), Pexels = grátis, música = grátis. Corte de custo máximo até validar.

---

## 10. Comandos

```bash
./venv/bin/python -m factory.cli pipeline --niche bom-dia --date today   # 4 slots
./venv/bin/python -m factory.cli pipeline --niche bom-dia --slot manha   # 1 slot
./venv/bin/python -m factory.cli voices --niche bom-dia                  # amostras de voz
python scripts/fetch_bible.py                                            # dataset Almeida

# Calibração do gate (fase copiloto)
./venv/bin/python -m factory.cli golden --niche bom-dia    # regressão do judge
./venv/bin/python -m factory.cli label pending             # runs sem veredito humano
./venv/bin/python -m factory.cli label set <run_id> PASS   # registra seu veredito
./venv/bin/python -m factory.cli label agreement           # concordância judge↔humano
```
