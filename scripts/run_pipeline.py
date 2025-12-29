#!/usr/bin/env python3
"""Segmented pipeline runner.

Implements the new architecture:
  - Each module writes its own outputs under tenant-aware output dirs
  - Optional commit after each module
"""

from __future__ import annotations

import argparse
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import List

import script_generate
import tts_generate
import video_render

from config import get_repo_root, get_output_dir
from git_commit import commit_paths


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _commit_enabled(cli_flag: bool | None) -> bool:
    if cli_flag is not None:
        return cli_flag
    if _bool_env("GITHUB_ACTIONS", False):
        return True
    return _bool_env("COMMIT_EACH_MODULE", False)


def _commit_module(module_name: str, topic_id: str, date_str: str) -> None:
    repo_root = get_repo_root()
    out_dir = get_output_dir(topic_id)
    tenant = os.environ.get("TENANT_ID", "0000000001")
    msg = f"[{tenant}] {topic_id} {date_str} - {module_name}"
    commit_paths(repo_root, [out_dir], msg)


def _run_validation(force: bool) -> bool:
    try:
        from system_validator import validate_system
        is_valid, result = validate_system(verbose=False)
        if is_valid:
            return True
        if force:
            return True
        return False
    except Exception:
        return True if force else True


def run_for_topic(
    topic_id: str,
    date_str: str | None = None,
    *,
    modules: List[str] | None = None,
    skip_validation: bool = False,
    force: bool = False,
    commit_each_module: bool | None = None,
) -> bool:
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    modules = modules or ["scripts", "images", "tts", "prepare_images", "video"]
    modules = [m.strip().lower() for m in modules if m.strip()]

    if not skip_validation:
        if not _run_validation(force=force):
            print("Validation failed")
            return False

    do_commit = _commit_enabled(commit_each_module)

    if "scripts" in modules:
        print("Module: scripts")
        if not script_generate.generate_for_topic(topic_id, date_str):
            return False
        if do_commit:
            _commit_module("scripts", topic_id, date_str)

    if "images" in modules:
        print("Module: images")
        try:
            from config import load_topic_config
            from global_config import IMAGES_SUBDIR
            from image_collector import collect_images_for_topic, DEFAULT_NUM_IMAGES

            cfg = load_topic_config(topic_id)
            out_dir = get_output_dir(topic_id)
            images_dir = out_dir / IMAGES_SUBDIR
            images_dir.mkdir(parents=True, exist_ok=True)
            # Prefer canonical search queries emitted by responses_api_generator (saved by scripts module).
            queries = None
            try:
                qpath = out_dir / f"{topic_id}-{date_str}.search_queries.json"
                if qpath.exists():
                    import json
                    data = json.loads(qpath.read_text(encoding="utf-8"))
                    qs = data.get("search_queries") or []
                    if isinstance(qs, list) and any(str(x).strip() for x in qs):
                        queries = [str(x).strip() for x in qs if str(x).strip()]
            except Exception:
                queries = None

            if not queries:
                queries = cfg.get("queries", [cfg.get("title", "")])
            collect_images_for_topic(
                topic_title=cfg.get("title", topic_id),
                topic_queries=queries,
                output_dir=images_dir,
                num_images=DEFAULT_NUM_IMAGES,
            )
        except Exception as e:
            print(f"Image collection failed (non-fatal): {e}")
            print(traceback.format_exc())
        if do_commit:
            _commit_module("images", topic_id, date_str)

    if "tts" in modules:
        print("Module: tts")
        if not tts_generate.generate_for_topic(topic_id, date_str):
            return False
        if do_commit:
            _commit_module("tts", topic_id, date_str)

    if "prepare_images" in modules:
        print("Module: prepare_images")
        from image_prepare import prepare_for_topic
        if not prepare_for_topic(topic_id, date_str):
            return False
        if do_commit:
            _commit_module("prepare_images", topic_id, date_str)

    if "video" in modules:
        print("Module: video")
        if not video_render.render_for_topic(topic_id, date_str):
            return False
        if do_commit:
            _commit_module("video", topic_id, date_str)

    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--date", default=None)
    ap.add_argument("--tenant", default=None)
    ap.add_argument("--modules", default=None)
    ap.add_argument("--skip-validation", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--commit-each-module", dest="commit_each_module", action="store_true", default=None)
    ap.add_argument("--no-commit-each-module", dest="commit_each_module", action="store_false", default=None)
    args = ap.parse_args()

    if args.tenant:
        os.environ["TENANT_ID"] = str(args.tenant).strip()
        os.environ.setdefault("USE_TENANT_OUTPUTS", "true")

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
