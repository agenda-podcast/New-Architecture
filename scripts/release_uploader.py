#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Release uploader (videos-only).

Workflow requirement:
- This script MUST run as the final step. If other steps upload ZIPs later, they will reappear.


Goal:
- Releases must contain ONLY final burned MP4 videos as flat assets (no folders, no zips, no archives).
- Even if other steps/modules uploaded .zip assets earlier, this script deletes ALL existing release assets first,
  then uploads ONLY the selected MP4s.

Behavior controls (env):
- RESET_RELEASE_ASSETS: default "1" => delete all existing assets on the release before uploading videos
- RENAME_ASSETS_TO_CODE: default "1" => rename assets to "<CODE>.mp4" (e.g., "R8.mp4") stripping topic/date/tenant/etc.
- FINAL_VIDEO_GLOB: default "outputs/**/*.mp4" => where to find candidate mp4s
- FINAL_VIDEO_EXCLUDE_PATTERNS: default "raw,tts,images,script,subs,subtitle,caption,debug,tmp,preview" (comma-separated)
"""
from __future__ import annotations

import os
import re
import sys
import json
import glob
import pathlib
import subprocess
from typing import List, Optional


def _run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def _env_flag(name: str, default: str = "0") -> bool:
    v = os.getenv(name, default).strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _get_repo() -> str:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is not set")
    return repo


def _get_tag() -> str:
    tag = os.getenv("RELEASE_TAG", "").strip()
    if not tag:
        tag = os.getenv("GITHUB_REF_NAME", "").strip()
    if not tag:
        raise RuntimeError("RELEASE_TAG (or GITHUB_REF_NAME) is not set")
    return tag


def _ensure_gh() -> None:
    try:
        _run(["gh", "--version"])
    except Exception as e:
        raise RuntimeError("GitHub CLI (gh) is required but not available") from e


def _get_release_json(tag: str) -> Optional[dict]:
    p = _run(["gh", "release", "view", tag, "--json", "id,tagName,assets"], check=False)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout or "{}")
    except Exception:
        return None


def _delete_all_assets(tag: str) -> None:
    rel = _get_release_json(tag)
    if not rel:
        return
    assets = rel.get("assets") or []
    for a in assets:
        asset_id = a.get("id")
        name = a.get("name")
        if not asset_id:
            continue
        try:
            _run(["gh", "api", "-X", "DELETE", f"repos/{_get_repo()}/releases/assets/{asset_id}"])
            print(f"[release] deleted asset: {name}")
        except subprocess.CalledProcessError as e:
            print(f"[release] WARN failed to delete asset {name}: {e.stderr.strip() if e.stderr else e}", file=sys.stderr)


def _ensure_release_exists(tag: str) -> None:
    rel = _get_release_json(tag)
    if rel:
        return
    _run(["gh", "release", "create", tag, "--title", tag, "--notes", ""])


def _is_final_video(path: str, exclude_patterns: List[str]) -> bool:
    lp = path.lower()
    if not lp.endswith(".mp4"):
        return False
    for pat in exclude_patterns:
        pat = pat.strip().lower()
        if pat and pat in lp:
            return False
    return True


_CODE_RE = re.compile(r'(?:(?:^|/)([A-Z]{1,2}\d{1,3}))(?:[^\w]|$)')


def _asset_name_from_path(p: str) -> str:
    m = _CODE_RE.search(p.replace("\\", "/"))
    if m:
        return f"{m.group(1)}.mp4"
    bn = os.path.basename(p)
    bn2 = re.sub(r'(^topic-\d+-\d{8}-)', '', bn, flags=re.I)
    bn2 = re.sub(r'(\.blender)?\.mp4$', '.mp4', bn2, flags=re.I)
    return bn2


def main() -> int:
    _ensure_gh()
    tag = _get_tag()

    reset_assets = _env_flag("RESET_RELEASE_ASSETS", "1")
    rename_to_code = _env_flag("RENAME_ASSETS_TO_CODE", "1")

    glob_pat = os.getenv("FINAL_VIDEO_GLOB", "outputs/**/*.mp4")
    exclude = os.getenv(
        "FINAL_VIDEO_EXCLUDE_PATTERNS",
        "raw,tts,images,script,subs,subtitle,caption,debug,tmp,preview"
    ).split(",")

    candidates = sorted(glob.glob(glob_pat, recursive=True))
    videos = [p for p in candidates if _is_final_video(p, exclude)]

    if not videos:
        print(f"[release] No final mp4 videos found (glob={glob_pat}).", file=sys.stderr)
        return 2

    _ensure_release_exists(tag)

    if reset_assets:
        print("[release] Resetting release assets: deleting ALL existing assets first...")
        _delete_all_assets(tag)

    used_names = set()
    for p in videos:
        name = _asset_name_from_path(p) if rename_to_code else os.path.basename(p)
        if name in used_names:
            stem = pathlib.Path(name).stem
            i = 2
            while f"{stem}_{i}.mp4" in used_names:
                i += 1
            name = f"{stem}_{i}.mp4"
        used_names.add(name)

        spec = f"{p}#{name}"
        print(f"[release] upload: {spec}")
        _run(["gh", "release", "upload", tag, spec, "--clobber"])

    print(f"[release] Done. Uploaded {len(videos)} video(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
