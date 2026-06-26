# Pro-Cult — geração em avanço (CLI mínimo, canal gospel)

Sem dashboard, sem API, sem fila/daemon. **Um comando gera vários vídeos em avanço**
e grava as pastas no filesystem. Foco: mínimo + produtividade.

## Como rodar
```bash
# 1 dia (hoje):
./venv/bin/python -m factory.cli pipeline --niche bom-dia --date today

# intervalo em avanço — semana / mês:
./venv/bin/python -m factory.cli pipeline --niche bom-dia --from 2026-06-26 --days 7
./venv/bin/python -m factory.cli pipeline --niche bom-dia --from 2026-06-26 --days 30
# (também aceita --to AAAA-MM-DD em vez de --days)

# run longo (mês ~3h): evita o Mac dormir
caffeinate -i ./venv/bin/python -m factory.cli pipeline --niche bom-dia --from <data> --days 30
```

## Comportamento
- Gera **sequencialmente** dia a dia; por dia, os 4 slots (manhã/tarde/noite + dia da semana),
  com **vozes distintas**.
- **Idempotente:** pula dias/slots que já têm `video.mp4`. Re-rodar = **retoma** (pega só o
  que falta). `--force` regera por cima.
- **Falha num item** → pula e segue; no fim imprime **resumo** (`X gerados · Y pulados · Z falhas`).
  Re-rodar pega os que falharam.
- Saída por slot: `output/AAAA-MM-DD/<slot>/` com **`video.mp4` + `caption.txt` + `hashtags.txt`**.

## Entrega (você revisa na sua máquina; depois você zipa e manda)
- No fim de uma run de intervalo, monta **automaticamente** uma **PASTA** em
  `output/_packages/<niche>_<from>_a_<to>/`.
- Dentro: vídeos renomeados `AAAA-MM-DD_slot.mp4` + **`index.html` (folha de postagem)** —
  lista ordenada com **preview do vídeo**, **data/hora sugerida** e **legenda+hashtags
  num campo com botão "Copiar"**.
- **Você** abre o `index.html` (duplo-clique, offline) pra **revisar**; quando aprovar,
  **zipa a pasta** e manda pra ela (WeTransfer/WhatsApp). Ela abre o mesmo html e posta na ordem.
- Re-empacotar sem gerar: `factory.cli package --niche bom-dia --from <data> --days <N>`.

## Versículos (não esgota)
- Pool curado em `data/verse_pool.json` (**358** versículos conhecidos/inspiradores,
  validados verbatim contra o dataset Almeida; afinidade de horário) — ~89 dias a 4/dia.
- `bible.reuse_after_days: 21` — versículo recicla após 21 dias (rede de segurança:
  o pool **nunca esgota**, degrada suave em vez de crashar).
- Expandir o pool: `python scratchpad/build_pool_400.py` (LLM gera refs → valida → grava).

## Comandos de apoio
```bash
python -m factory.cli golden --niche bom-dia        # regressão do judge (eval)
python -m factory.cli voices --niche bom-dia        # amostras do pool de vozes
python -m factory.cli label {pending|set <id> PASS|FAIL|agreement}   # calibração do gate
python scripts/fetch_bible.py                       # baixa o dataset Almeida
```

## Fora de escopo (sem otimização prematura)
Dashboard, API, fila/daemon, storage remoto, multi-canal, RAG, Seedance — nada disso
agora; só quando (e se) houver necessidade real.
