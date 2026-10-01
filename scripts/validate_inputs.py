"""Validate a starter task and associated CSV; optional report output."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from _core import validate_bundle, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        report = validate_bundle(args.task)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {"valid": False, "status": "blocked", "errors": [str(exc)], "prediction_performed": False}
    if args.out:
        if args.out.exists():
            parser.error("Output already exists; choose a new filename")
        write_json(args.out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
