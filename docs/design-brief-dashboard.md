# Design Brief: Pro-Cult Dashboard (review & ship)

> Produced by `/impeccable shape dashboard`. Confirmed by the owner.
> Anchored in PRODUCT.md (register: product), DESIGN.md (seed), and docs/BUILD-PLAN.md (Fase 3).
> Hand off to `/impeccable craft dashboard` to build.

## 1. Feature summary

A calm, light, desktop-browser dashboard for one person (the owner's non-technical
wife) to drive the video factory: pick a span of days, kick off generation, walk away,
and later return to review finished portrait videos and hand them off to TikTok's
scheduler. It is the human end of an automated pipeline. Pure logistics for now:
generate, review, download, copy the caption, regenerate a bad one. No verdict labeling.

## 2. Primary user action

**Take a finished video and get it onto TikTok** (download the file + copy its caption
text). Everything else (generating, waiting, regenerating) exists to deliver a tile to
that moment.

## 3. Design direction

- **Color strategy: Restrained** (project default, confirmed in DESIGN.md). Warm
  sand/oatmeal neutrals, a single sage accent reserved for the one primary action per
  view. The portrait video thumbnails are the only saturated things on screen.
- **Theme scene sentence:** *"The wife, mid-morning at the kitchen table on a MacBook,
  coffee in hand and unhurried, glancing through last night's finished videos in bright
  daylight to decide which to send to TikTok."* Forces a **light** theme. No dark mode.
- **Anchor references:** **Things 3** (serene, forgiving, calm task surface),
  **Apple Photos** (a light grid of portrait media where the content is the hero and the
  chrome disappears), **Craft** (warm paper surface, plain humanist type, content-first).

## 4. Scope

Production-ready build (React/Vite + FastAPI, single-origin, simple password). Breadth:
the **whole review-and-ship surface** as one coherent flow (generate control + results
surface + per-video and per-day actions), single channel (gospel) for now with room for
more. Shipped-quality, all states. Time intent: build it to be the daily driver.

## 5. Layout strategy

One scrolling page, no sidebar (a sidebar full of icons is an explicit anti-reference,
and there's one channel). Top to bottom:

- **Quiet header:** the channel name, plainly. Not a nav bar.
- **Generate band:** a date-range picker + a single sage **Gerar** button. The one place
  the accent lives at the top.
- **Results surface, grouped by day** (chosen unit: "by date range first"): each day is a
  labeled section (e.g. "Quinta, 26 de junho"), containing up to 4 **video tiles**
  (Manhã · Tarde · Noite · Semana). Day sections stack down the page in date order.
- **Generation status** woven in, not a separate babysitting screen: a calm persistent
  strip (e.g. *"Gerando… 12 de 28 prontos"*) plus per-tile state, since she kicks it off
  and walks away. Polling restores state when she returns.

Spacing breathes (no cramped SaaS density); the tile grid is the rhythm.

**Signature component, the video tile:** a portrait 9:16 thumbnail as the hero, slot
label, state, and its actions (preview, download, copy caption, regenerate). Each **day
section** also carries a quiet "grab the whole day" shortcut (download all + copy all),
because both granularities were requested.

## 6. Key states

- **First run / empty:** no range generated yet. Teaches the one move: pick dates, press
  Gerar. Warm, not "nothing here."
- **Queued:** tiles appear as calm placeholders ("Na fila").
- **Generating:** per-tile gentle progress; overall count in the status strip. She can leave.
- **Ready:** thumbnail fades in (Responsive motion), actions become available.
- **Partial day:** some of the 4 slots ready, others still generating. Section shows both calmly.
- **Failed slot:** a tile that errored, with a plain, non-alarming "Gerar de novo."
  Recoverable, never scary (Forgiving-by-default principle).
- **Regenerating:** the tile returns to a generating state in place.
- **Backend down / offline (LAN/Tailscale):** a calm, plain message, not a stack trace.
- **Password gate:** a single warm, simple unlock screen.

## 7. Interaction model

Pick range, press **Gerar** (sage), tiles populate as "na fila," then fade to ready one by
one. She can close the laptop and return; polling rehydrates progress. Click a thumbnail
to **preview** the portrait video larger (a focused lightbox is justified here because the
video is the content-hero, not a lazy modal). Per tile: **Baixar**, **Copiar legenda**,
**Gerar de novo**, each with a quiet "Copiado"/"Baixado" confirmation. At day level:
**Baixar o dia** and **Copiar tudo do dia**. Transitions 150 to 250ms, gentle fades, no
choreography.

## 8. Content requirements (all plain PT-BR)

- Actions: `Gerar`, `Gerar de novo`, `Baixar`, `Baixar o dia`, `Copiar legenda`,
  `Copiar tudo do dia`.
- States: `Na fila`, `Gerando…`, `Pronto`, `Falhou`, `Gerando… X de Y prontos`.
- Slot labels: `Manhã`, `Tarde`, `Noite`, `Semana`.
- Empty state: a warm one-liner that teaches the move (e.g. *"Escolha os dias e toque em
  Gerar para começar."*).
- Error/offline: plain reassurance, no jargon (e.g. *"Não consegui falar com o computador
  que gera os vídeos. Tente de novo daqui a pouco."*).
- **Caption insight:** the pipeline outputs `title.txt` + `caption.txt` + `hashtags.txt`
  separately, but TikTok takes a single caption box. Recommendation: one **Copiar legenda**
  that assembles title + caption + hashtags into the exact text she pastes, rather than
  three copy buttons (see open question 1).

## 9. Recommended references for implementation

- `product.md` register: familiar affordances, full state vocabulary, Restrained color,
  150 to 250ms motion.
- Layout/spatial reference: the day-grouped tile grid and rhythm.
- Interaction reference: the generate, poll, review, ship flow and copy/download feedback.
- Motion reference: gentle ready-state fade-ins (Responsive, no choreography).
- `harden.md`: the failed-slot, partial-day, and backend-down states are where this earns trust.

## 10. Open questions (resolve during build)

1. **Caption copy:** one combined "Copiar legenda" (recommended) vs separate
   título/legenda/hashtags buttons?
2. **Generate scope:** does **Gerar** on a range queue the whole span at once (assumed),
   or day-by-day?
3. **Regenerate semantics:** does "Gerar de novo" pull a fresh verse/voice or keep the
   same content? (affects expectation and copy)
4. **Preview:** focused lightbox vs expand-in-place on the tile?
5. **Range size:** realistic max days in one go (affects scroll length / lazy-load).
