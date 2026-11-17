"""Command line: ``nudgewright compose facts.json`` and ``nudgewright signals``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import replace

from . import __version__
from .composer import compose_many
from .loader import load_facts_file, load_festivals
from .signals import catalogue


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nudgewright", description="Explainable, guard-railed customer message lines."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    comp = sub.add_parser("compose", help="write a line for every customer in a facts JSON file")
    comp.add_argument("facts", help="path to the facts JSON file")
    comp.add_argument("--festivals", help="extra festival calendar JSON (a list, or {'festivals': [...]})")
    comp.add_argument("--text", action="store_true", help="print 'id: line' and a summary instead of JSON")
    sig = sub.add_parser("signals", help="list the signal catalogue")
    sig.add_argument("--live", action="store_true", help="only signals the composer uses today")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "signals":
            rows = [r for r in catalogue() if r["status"] == "live" or not args.live]
            print(json.dumps(rows, indent=2, ensure_ascii=False))
            return 0
        ctx, customers = load_facts_file(args.facts)
        if args.festivals:
            ctx = replace(ctx, festivals=[*ctx.festivals, *load_festivals(args.festivals)])
        results = compose_many(ctx, customers)
    except (OSError, ValueError) as exc:
        print(f"nudgewright: {exc}", file=sys.stderr)
        return 2
    if args.text:
        for cid, res in results.items():
            print(f"{cid}: {res.line or '(no line)'}")
            print(f"  {res.summary()}")
    else:
        print(json.dumps([r.why() for r in results.values()], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
