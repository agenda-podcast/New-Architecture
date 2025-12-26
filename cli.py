#!/usr/bin/env python3
"""Unified CLI entry point for the segmented pipeline."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    ap = argparse.ArgumentParser(prog="cli.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    runp = sub.add_parser("run", help="Run segmented pipeline")
    runp.add_argument("--topic", required=True)
    runp.add_argument("--date", default=None)
    runp.add_argument("--tenant", default=None)
    runp.add_argument("--modules", default=None)
    runp.add_argument("--skip-validation", action="store_true")
    runp.add_argument("--force", action="store_true")
    runp.add_argument("--commit-each-module", action="store_true", default=None)
    runp.add_argument("--no-commit-each-module", action="store_false", dest="commit_each_module", default=None)

    valp = sub.add_parser("validate", help="Run system validation")
    valp.add_argument("--force", action="store_true")

    args = ap.parse_args()

    if args.cmd == "validate":
        from run_pipeline import _run_validation
        return 0 if _run_validation(force=args.force) else 1

    if args.tenant:
        os.environ["TENANT_ID"] = str(args.tenant).strip()
        os.environ.setdefault("USE_TENANT_OUTPUTS", "true")

    from run_pipeline import run_for_topic

    modules = None
    if args.modules:
        modules = [m.strip() for m in args.modules.split(",") if m.strip()]

    ok = run_for_topic(
        args.topic,
        args.date,
        modules=modules,
        skip_validation=args.skip_validation,
        force=args.force,
        commit_each_module=args.commit_each_module,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
