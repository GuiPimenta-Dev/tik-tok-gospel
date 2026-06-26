"""CLI da fábrica. Subcomandos:

  # 1 dia:
  python -m factory.cli pipeline --niche bom-dia --date today [--slot manha]
  # intervalo em avanço (idempotente; pula o que já existe, --force regera):
  python -m factory.cli pipeline --niche bom-dia --from 2026-06-26 --days 7    # semana
  python -m factory.cli pipeline --niche bom-dia --from 2026-06-26 --days 30   # mês
  #   (dica p/ runs longos: caffeinate -i ./venv/bin/python -m factory.cli ...)
  python -m factory.cli voices   --niche bom-dia
  python -m factory.cli golden   --niche bom-dia
  python -m factory.cli label {pending | set <run_id> PASS|FAIL | agreement}
"""
import argparse
import os
from datetime import datetime, timedelta

from .config import load_config, path
from .domain import evaluation, packaging, pipeline
from .adapters import store, tts

VOICE_SAMPLE = ("Boa noite. Que a paz de Deus guarde o seu coração e a sua mente. "
                "Descanse tranquilo, pois tudo tem o seu tempo.")


def _resolve_dates(args) -> list:
    """Resolve a lista de datas a partir de --from/--days/--to (ou --date pra 1 dia)."""
    today = datetime.now().strftime("%Y-%m-%d")
    start = args.from_ or (args.date if args.date and args.date != "today" else today)
    s = datetime.strptime(start, "%Y-%m-%d")
    if args.days:
        return [(s + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(args.days)]
    if args.to:
        e = datetime.strptime(args.to, "%Y-%m-%d")
        n = max(1, (e - s).days + 1)
        return [(s + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]
    return [start]


def _cmd_pipeline(args):
    cfg = load_config(args.niche)
    dates = _resolve_dates(args)
    pipeline.run_range(cfg, args.niche, dates, only_slot=args.slot, force=args.force)


def _cmd_package(args):
    cfg = load_config(args.niche)
    packaging.build_package(cfg, args.niche, _resolve_dates(args))


def _cmd_voices(args):
    cfg = load_config(args.niche)
    out = path("output", "voice-samples")
    os.makedirs(out, exist_ok=True)
    for v in cfg["tts"]["voices"]:
        dest = os.path.join(out, f"{v['gender'].upper()}_{v['name']}_{v['id']}.mp3")
        try:
            tts.tts(VOICE_SAMPLE, dest, cfg, v["id"])
            print(f"OK  {v['name']:<8} ({v['gender']}) -> {dest}")
        except Exception as e:  # noqa: BLE001
            print(f"ERRO {v['name']}: {e}")


def _cmd_golden(args):
    ok = evaluation.run_golden(load_config(args.niche))
    raise SystemExit(0 if ok else 1)


def _cmd_label(args):
    store.init()
    if args.action == "pending":
        rows = store.list_pending()
        if not rows:
            print("Nada pendente. 🎉")
        for r in rows:
            print(f"  {r['run_id']}  {r['slot']:<6} judge={r['judge_verdict']:<4} "
                  f"{r['verse_ref']}  ({r['ts'][:19]})")
    elif args.action == "set":
        n = store.set_human_verdict(args.run_id, args.verdict)
        print(f"OK ({n} atualizada(s))" if n else f"run_id não encontrado: {args.run_id}")
    elif args.action == "agreement":
        rows = store.agreement()
        if not rows:
            print("Sem labels humanos ainda.")
        for r in rows:
            print(f"  rubric {r['rubric_version']}: concordância "
                  f"{(r['concordancia'] or 0):.0%}  (n={r['n']})")


def main():
    ap = argparse.ArgumentParser(prog="factory")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pipeline", help="gera vídeos (1 dia ou um intervalo em avanço)")
    p.add_argument("--niche", required=True)
    p.add_argument("--date", default="today", help="1 dia (default: hoje)")
    p.add_argument("--from", dest="from_", help="data inicial AAAA-MM-DD do intervalo")
    p.add_argument("--days", type=int, help="quantos dias a partir de --from (7=semana, 30=mês)")
    p.add_argument("--to", help="data final AAAA-MM-DD (alternativa a --days)")
    p.add_argument("--slot", help="manha|tarde|noite|semana (omitir = todos)")
    p.add_argument("--force", action="store_true", help="regera mesmo se já existir")
    p.set_defaults(func=_cmd_pipeline)

    pk = sub.add_parser("package", help="re-empacota um intervalo num zip (sem gerar)")
    pk.add_argument("--niche", required=True)
    pk.add_argument("--date", default="today")
    pk.add_argument("--from", dest="from_")
    pk.add_argument("--days", type=int)
    pk.add_argument("--to")
    pk.set_defaults(func=_cmd_package)

    v = sub.add_parser("voices", help="gera amostras do pool de vozes")
    v.add_argument("--niche", default="bom-dia")
    v.set_defaults(func=_cmd_voices)

    g = sub.add_parser("golden", help="regressão do judge (golden set)")
    g.add_argument("--niche", default="bom-dia")
    g.set_defaults(func=_cmd_golden)

    la = sub.add_parser("label", help="calibração do gate (veredito humano)")
    la.add_argument("action", choices=["pending", "set", "agreement"])
    la.add_argument("run_id", nargs="?")
    la.add_argument("verdict", nargs="?", choices=["PASS", "FAIL"])
    la.set_defaults(func=_cmd_label)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
