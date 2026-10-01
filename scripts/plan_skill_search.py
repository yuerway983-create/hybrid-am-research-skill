"""Prepare an OFFLINE GitHub sub-skill search plan. No network/execution."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from _core import QUERIES, load_json, search_plan, write_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=sorted(QUERIES))
    parser.add_argument("--registry", type=Path, default=ROOT / "registry/seed_candidates.json")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = search_plan(load_json(args.registry), args.stage)
    if args.out:
        if args.out.exists():
            parser.error("Output exists; choose a new path")
        write_json(args.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
