#!/usr/bin/env python3
"""
Tenant output publishing: create one ZIP per output type and upload to a persistent
tenant release (GitHub Releases assets are flat; directory structure lives inside ZIPs).

Assets created (examples):
  Assets_<TENANT_ID>_Text_topic-01_YYYYMMDD.zip
  Assets_<TENANT_ID>_JSON_topic-01_YYYYMMDD.zip
  Assets_<TENANT_ID>_Subtitles_topic-01_YYYYMMDD.zip
  Assets_<TENANT_ID>_Audio_topic-01_YYYYMMDD.zip
  Assets_<TENANT_ID>_Video_topic-01_YYYYMMDD.zip

Inside each zip:
  Assets/<TENANT_ID>/Outputs/<topic>/<YYYYMMDD>/<Type>/<filename>
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

try:
    # Works when executed from repo root
    from scripts.tenant_assets import ensure_release, upload_asset
except Exception:
    # Works when executed from within scripts/
    from tenant_assets import ensure_release, upload_asset


@dataclass(frozen=True)
class OutputType:
    name: str
    patterns: Tuple[str, ...]


OUTPUT_TYPES: Tuple[OutputType, ...] = (
    OutputType("Text", ("*.txt",)),
    OutputType("JSON", ("*.json",)),
    OutputType("Subtitles", ("*.srt", "*.vtt")),
    OutputType("Audio", ("*.m4a", "*.mp3", "*.wav")),
    OutputType("Video", ("*.mp4", "*.mov", "*.mkv")),
)


def tenant_id() -> str:
    return os.getenv("TENANT_ID", "0000000001")


def tenant_release_tag(tid: str) -> str:
    return os.getenv("TENANT_ASSETS_RELEASE_TAG", f"tenant-assets-{tid}")


def _collect_files(topic_dir: Path, topic: str, date_yyyymmdd: str, patterns: Tuple[str, ...]) -> List[Path]:
    """Collect output files for a topic/date.

    Notes:
    - GitHub Actions runners have historically produced outputs either directly under
      outputs/<topic>/ or in nested subfolders. We therefore search recursively.
    - Some patterns may include recursive globs (e.g., "**/*.mp4"). Pathlib has strict
      rules: "**" must be a full path component, so we avoid constructing invalid
      patterns like "<prefix>***/*.mp4".
    """

    import re

    files: List[Path] = []
    prefix = f"{topic}-{date_yyyymmdd}"

    # Derive a list of file extensions from the provided patterns.
    exts: List[str] = []
    for pat in patterns:
        m = re.search(r"(\.[A-Za-z0-9]+)$", pat)
        if m:
            exts.append(m.group(1).lower())

    # Primary: recursively find files that start with <topic>-<date> and have allowed extensions.
    if exts:
        for ext in sorted(set(exts)):
            files.extend(sorted(topic_dir.rglob(f"{prefix}*{ext}")))

    # Secondary: include any files that match the patterns directly (for cases without prefix).
    for pat in patterns:
        # Use rglob so "**/*.ext" is always valid.
        try:
            files.extend(sorted(topic_dir.rglob(pat)))
        except ValueError:
            # Fallback: treat as simple basename glob.
            files.extend(sorted(topic_dir.glob(pat.split('/')[-1])))

    # De-dupe while preserving order (by path, not only filename).
    seen: set[str] = set()
    out: List[Path] = []
    for f in files:
        if f.is_file():
            key = str(f.resolve())
            if key not in seen:
                seen.add(key)
                out.append(f)
    return out


def build_zip_for_type(
    tid: str,
    topic: str,
    date_yyyymmdd: str,
    out_type: OutputType,
    files: List[Path],
    build_dir: Path,
) -> Path:
    """Create a zip asset for an output type."""
    asset_name = f"Assets_{tid}_{out_type.name}_{topic}_{date_yyyymmdd}.zip"
    zip_path = build_dir / asset_name

    # Create staging folder with desired structure
    base = build_dir / "Assets" / tid / "Outputs" / topic / date_yyyymmdd / out_type.name
    base.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, base / f.name)

    # Zip the Assets/ root
    assets_root = build_dir / "Assets"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in assets_root.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(build_dir).as_posix())

    # Cleanup the staging 'Assets' tree, keep zip only
    shutil.rmtree(assets_root, ignore_errors=True)
    return zip_path


def publish_outputs_per_type(
    outputs_root: Path,
    topic: str,
    date_yyyymmdd: str,
    *,
    tid: str | None = None,
) -> Dict[str, str]:
    """Build and upload one zip per output type for a given topic and date."""
    tid = tid or tenant_id()
    tag = tenant_release_tag(tid)
    ensure_release(tag, title=f"Tenant Assets ({tid})", notes=f"Persistent assets store for tenant {tid}")

    topic_dir = outputs_root / topic
    if not topic_dir.exists():
        raise FileNotFoundError(f"Topic outputs directory not found: {topic_dir}")

    results: Dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="tenant_outputs_") as td:
        build_dir = Path(td)
        for out_type in OUTPUT_TYPES:
            files = _collect_files(topic_dir, topic, date_yyyymmdd, out_type.patterns)
            if not files:
                continue
            zip_path = build_zip_for_type(tid, topic, date_yyyymmdd, out_type, files, build_dir)
            upload_asset(tag, zip_path, clobber=True)
            results[out_type.name] = zip_path.name
    return results
