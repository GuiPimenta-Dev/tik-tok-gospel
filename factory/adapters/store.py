"""SQLite: store de eval (+ métricas, Fase 2) e ledger de versículos usados.

Dois arquivos:
  data/evals.sqlite       -> tabelas evals, metrics
  data/used_verses.sqlite -> tabela used_verses (ledger)
"""
import json
import sqlite3

from ..config import path

EVALS_DB = path("data", "evals.sqlite")
LEDGER_DB = path("data", "used_verses.sqlite")

EVALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS evals (
  run_id          TEXT PRIMARY KEY,
  ts              TEXT NOT NULL,
  niche           TEXT NOT NULL,
  slot            TEXT NOT NULL,
  verse_ref       TEXT NOT NULL,
  verse_text      TEXT NOT NULL,
  frame_variants  TEXT NOT NULL,
  judge_scores    TEXT NOT NULL,
  chosen_idx      INTEGER,
  hard_checks     TEXT NOT NULL,
  judge_verdict   TEXT NOT NULL,
  judge_reasons   TEXT,
  human_verdict   TEXT,
  prompt_version  TEXT NOT NULL,
  rubric_version  TEXT NOT NULL,
  model_id        TEXT NOT NULL,
  content_hash    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
  content_hash    TEXT PRIMARY KEY,
  run_id          TEXT,
  views           INTEGER,
  completion_rate REAL,
  watch_time_s    REAL,
  shares          INTEGER,
  pulled_at       TEXT
);
"""

LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS used_verses (
  ref       TEXT PRIMARY KEY,
  run_id    TEXT,
  used_at   TEXT NOT NULL
);
"""


def _conn(db_path: str, schema: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(schema)
    return conn


def init():
    _conn(EVALS_DB, EVALS_SCHEMA).close()
    _conn(LEDGER_DB, LEDGER_SCHEMA).close()


# ---- ledger de versículos ----

def is_used(ref: str) -> bool:
    with _conn(LEDGER_DB, LEDGER_SCHEMA) as c:
        return c.execute("SELECT 1 FROM used_verses WHERE ref=?", (ref,)).fetchone() is not None


def mark_used(ref: str, run_id: str, used_at: str):
    with _conn(LEDGER_DB, LEDGER_SCHEMA) as c:
        c.execute(
            "INSERT OR REPLACE INTO used_verses(ref, run_id, used_at) VALUES (?,?,?)",
            (ref, run_id, used_at),
        )


# ---- store de eval ----

def record_eval(row: dict):
    """Grava uma run. Campos dict/list são serializados em JSON."""
    for k in ("frame_variants", "judge_scores", "hard_checks"):
        if not isinstance(row[k], str):
            row[k] = json.dumps(row[k], ensure_ascii=False)
    cols = ",".join(row.keys())
    qs = ",".join("?" * len(row))
    with _conn(EVALS_DB, EVALS_SCHEMA) as c:
        c.execute(f"INSERT OR REPLACE INTO evals ({cols}) VALUES ({qs})", tuple(row.values()))


def set_human_verdict(run_id: str, verdict: str) -> int:
    with _conn(EVALS_DB, EVALS_SCHEMA) as c:
        cur = c.execute("UPDATE evals SET human_verdict=? WHERE run_id=?", (verdict, run_id))
        return cur.rowcount


def list_pending(limit: int = 50) -> list:
    """Runs sem veredito humano (fase copiloto)."""
    with _conn(EVALS_DB, EVALS_SCHEMA) as c:
        rows = c.execute(
            "SELECT run_id, ts, slot, verse_ref, judge_verdict FROM evals "
            "WHERE human_verdict IS NULL ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def agreement() -> list:
    """Concordância judge↔humano por versão de rubric (gatilho de promoção do gate)."""
    with _conn(EVALS_DB, EVALS_SCHEMA) as c:
        rows = c.execute(
            "SELECT rubric_version, "
            "AVG(judge_verdict = human_verdict) AS concordancia, COUNT(*) AS n "
            "FROM evals WHERE human_verdict IS NOT NULL GROUP BY rubric_version"
        ).fetchall()
        return [dict(r) for r in rows]
