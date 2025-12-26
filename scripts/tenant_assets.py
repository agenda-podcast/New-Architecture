#!/usr/bin/env python3
"""
Helpers for storing and retrieving artifacts from GitHub Releases.

Important constraint:
- GitHub Release "assets" are a flat list of files in the UI (no folders).
- If you want a folder hierarchy like Assets/<TENANT_ID>/..., you must store it
  *inside* a ZIP (or tar) asset.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def get_bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1","true","yes","y","on")

def tenant_assets_enabled() -> bool:
    # Default TRUE; caller can disable to avoid gh usage and downloads.
    return get_bool_env("ENABLE_TENANT_ASSETS", True)


def _run(cmd: list[str], env: Optional[dict] = None) -> Tuple[int, str, str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    p = subprocess.run(cmd, capture_output=True, text=True, env=merged)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def gh_available() -> bool:
    if not tenant_assets_enabled():
        return False
    rc, _, _ = _run(["gh", "--version"])
    return rc == 0


def release_exists(tag: str) -> bool:
    rc, _, _ = _run(["gh", "release", "view", tag])
    return rc == 0


def ensure_release(tag: str, title: str, notes: str = "") -> None:
    """Ensure a GitHub Release exists for the given tag.

    Notes:
    - This function is safe to call repeatedly.
    - It does not delete or overwrite an existing release.
    - If tenant assets are disabled, it is a no-op.
    """

    if not tenant_assets_enabled():
        print("  ⓘ Tenant assets disabled (ENABLE_TENANT_ASSETS=false); skipping ensure_release")
        return
    if release_exists(tag):
        return
    rc, _, err = _run([
        "gh", "release", "create", tag,
        "--title", title,
        "--notes", notes or f"Persistent assets store for {tag}"
    ])
    if rc != 0:
        raise RuntimeError(f"Failed to create release {tag}: {err}")


def upload_asset(tag: str, file_path: Path, clobber: bool = True) -> None:
    args = ["gh", "release", "upload", tag, str(file_path)]
    if clobber:
        args.append("--clobber")
    rc, _, err = _run(args)
    if rc != 0:
        raise RuntimeError(f"Failed to upload asset to {tag}: {file_path.name}: {err}")


def download_asset(tag: str, asset_name: str, dest_dir: Path) -> Path:
    """
    Download a specific release asset by name into dest_dir.
    Returns the downloaded file path.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run([
        "gh", "release", "download", tag,
        "--pattern", asset_name,
        "--dir", str(dest_dir)
    ])
    if rc != 0:
        raise RuntimeError(f"Failed to download asset {asset_name} from {tag}: {err or out}")
    fp = dest_dir / asset_name
    if not fp.exists():
        # gh may preserve original filename; best-effort locate
        for p in dest_dir.glob("*"):
            if p.name == asset_name:
                return p
        raise RuntimeError(f"Downloaded, but could not locate {asset_name} in {dest_dir}")
    return fp


def delete_asset(tag: str, asset_name: str) -> bool:
    """Delete a release asset if it exists. Returns True if deleted."""
    # gh returns non-zero if asset is not found; treat that as "not deleted".
    rc, _, err = _run(["gh", "release", "delete-asset", tag, asset_name, "-y"])
    if rc == 0:
        return True
    # Non-fatal; caller may be cleaning up legacy assets.
    if err:
        print(f"  ⓘ Could not delete asset (may not exist): tag={tag} asset={asset_name}: {err}")
    return False