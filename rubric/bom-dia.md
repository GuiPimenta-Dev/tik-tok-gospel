# Rubric do LLM-judge — nicho bom-dia

> Versionado no git. Mudou o rubric → rode a regressão do golden set antes de usar.
> Versão: v1

O judge avalia cada **variação de frase motivacional** e devolve, por variante:
`{ "score": 0-10, "pass": true|false, "reasons": "..." }`.

## Critérios (a variação só passa se atender TODOS)

> Cada variação tem **gancho** (1ª frase na tela, prende em 2s), **frase**
> (motivacional) e **cta** (chamada final de engajamento). Avalie os três.

0. **Gancho (peso ALTO).** Curto (3–8 palavras), endereçamento direto e acolhedor,
   faz a pessoa sentir que é pra ela. Penalize gancho genérico ("bom dia a todos")
   ou que seja só a saudação. **Eliminatório:** nada de barganha/medo/promessa
   ("compartilhe ou perde a bênção", "assista até o fim pra receber").
0b. **CTA gentil.** Convida a comentar/compartilhar sem barganha nem culpa
   ("Marque alguém 🙏" ok; "compartilhe ou…" reprova a variação).
1. **Coerência com o versículo.** Gancho e frase conversam de fato com o versículo e a
   saudação — não são genéricos nem desconectados. (peso alto)
2. **Tom do horário.** Bate com o tom configurado do slot (manhã = esperançoso/
   energético; tarde = leve/grato; noite = calmo/reflexivo).
3. **Português correto.** Sem erro de gramática/ortografia. Linguagem acolhedora,
   adequada a público 50+ religioso.
3b. **Linguagem simples (peso ALTO).** Palavras do dia a dia, que uma avó entenderia
   sem dicionário; frases curtas. Penalize fortemente palavras rebuscadas/literárias
   ("serenidade", "contemplai", "alvorada", "plenitude"). Meio-termo: simples mas com
   um toque inspirador. Entre variações de mérito parecido, **prefira a mais simples**.
4. **Brand-safe (eliminatório):**
   - SEM promessa de cura, saúde ou ganho financeiro;
   - SEM teologia polêmica, denominacional-divisiva ou sensacionalista;
   - SEM política, medo, culpa ou manipulação;
   - SEM citar/parafrasear o versículo de forma que distorça o texto bíblico.
5. **Tamanho.** Cabe na tela e na narração (curta, ~1–3 frases).

## Saída esperada (JSON)

```json
{
  "variants": [
    {"idx": 0, "score": 8, "pass": true,  "reasons": "..."},
    {"idx": 1, "score": 4, "pass": false, "reasons": "tom errado p/ noite"},
    {"idx": 2, "score": 7, "pass": true,  "reasons": "..."}
  ],
  "chosen_idx": 0,
  "verdict": "PASS"
}
```

Se nenhuma variante passar → `chosen_idx: null`, `verdict: "FAIL"`.

## Notas de evolução (Fase 4)
Quando o loop de métricas estiver ativo, exemplos de frases que tiveram alta
retenção/compartilhamento viram few-shots positivos AQUI, e o rubric é ajustado
com base no que de fato performou — não em opinião.
