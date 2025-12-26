#!/usr/bin/env python3
"""
Preprocessed image cache backed by GitHub Release assets.

We store composites (for undersized source images) in a ZIP asset named:
  Assets_<TENANT_ID>_Images_<WxH>.zip

Inside the ZIP we keep the requested directory hierarchy:
  Assets/<TENANT_ID>/Images/<WxH>/processed/<composite files>
  Assets/<TENANT_ID>/Images/<WxH>/processed/manifest_<WxH>.json

Why ZIP?
- GitHub Release assets are flat in the UI (no folders). Zips preserve structure.
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tenant_assets import ensure_release, download_asset, upload_asset, gh_available


DEFAULT_TENANT_ID = "0000000001"


def get_bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

def cache_reset_enabled() -> bool:
    # Default TRUE to minimize persistent storage / downloads unless explicitly disabled.
    return get_bool_env("CACHE_RESET", True)

def images_cache_enabled() -> bool:
    # Image cache via tenant assets can be disabled globally or via cache reset.
    if cache_reset_enabled():
        return False
    if not get_bool_env("ENABLE_TENANT_ASSETS", True):
        return False
    return get_bool_env("ENABLE_TENANT_ASSETS_CACHE", True)


def get_tenant_id() -> str:
    return os.environ.get("TENANT_ID", DEFAULT_TENANT_ID).strip() or DEFAULT_TENANT_ID


def get_tenant_assets_release_tag(tenant_id: Optional[str] = None) -> str:
    tenant_id = tenant_id or get_tenant_id()
    return os.environ.get("TENANT_ASSETS_RELEASE_TAG", f"tenant-assets-{tenant_id}")


def assets_enabled() -> bool:
    v = os.environ.get("ENABLE_TENANT_ASSETS_CACHE", "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def images_asset_name(tenant_id: str, w: int, h: int) -> str:
    return f"Assets_{tenant_id}_Images_{w}x{h}.zip"


def _manifest_path(cache_dir: Path, w: int, h: int) -> Path:
    # cache_dir is the local processed-images directory
    return cache_dir / f"manifest_{w}x{h}.json"


def _local_composites_dir(cache_dir: Path) -> Path:
    # cache_dir is the local processed-images directory
    return cache_dir


def _zip_internal_prefix(tenant_id: str, w: int, h: int) -> str:
    return f"Assets/{tenant_id}/Images/{w}x{h}/processed/"


def validate_local_manifest(manifest_path: Path, source_images: List[Path]) -> bool:
    if not manifest_path.exists():
        return False
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    # Build quick lookup: name -> (size, mtime, mode, out)
    by_name: Dict[str, dict] = {e["source_name"]: e for e in data.get("entries", []) if "source_name" in e}
    if len(by_name) < len(source_images):
        return False

    for src in source_images:
        st = src.stat()
        e = by_name.get(src.name)
        if not e:
            return False
        if int(e.get("source_size", -1)) != int(st.st_size):
            return False
        # allow small mtime skew
        if abs(float(e.get("source_mtime", -1.0)) - float(st.st_mtime)) > 1.0:
            return False
        if e.get("mode") == "composite":
            out_file = e.get("out_file")
            if not out_file:
                return False
            out_path = manifest_path.parent / out_file
            if not out_path.exists() or out_path.stat().st_size == 0:
                return False

    return True


def restore_images_cache_from_release(source_images: List[Path], w: int, h: int, cache_dir: Path) -> bool:
    """Attempt to restore the processed-images cache from the tenant Release asset.

    cache_dir is the *local processed-images directory* (e.g. outputs/.../processed_images).
    """
    if not images_cache_enabled():
        print("  ⓘ Tenant images cache restore disabled (CACHE_RESET or ENABLE_TENANT_ASSETS_CACHE=false)")
        return False

    if not assets_enabled() or not gh_available():
        return False

    tenant_id = get_tenant_id()
    tag = get_tenant_assets_release_tag(tenant_id)
    asset = images_asset_name(tenant_id, w, h)

    tmp_dir = cache_dir / "_download_tmp"
    try:
        ensure_release(tag, title=f"Tenant Assets {tenant_id}", notes="Persistent cache for preprocessed images & bundles.")

        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        zip_path = download_asset(tag, asset, tmp_dir)

        composites_dir = _local_composites_dir(cache_dir)
        composites_dir.mkdir(parents=True, exist_ok=True)

        prefix = _zip_internal_prefix(tenant_id, w, h)

        with zipfile.ZipFile(zip_path, "r") as z:
            members = [m for m in z.namelist() if m.startswith(prefix)]
            if not members:
                return False
            for mname in members:
                rel = mname[len(prefix):]
                if not rel:
                    continue
                dest = composites_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(mname) as srcf, open(dest, "wb") as outf:
                    shutil.copyfileobj(srcf, outf)

        manifest = _manifest_path(cache_dir, w, h)
        return validate_local_manifest(manifest, source_images)

    except Exception as e:
        print(f"  ⓘ Tenant assets restore skipped/failed: {e}")
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def publish_images_cache_to_release(source_images: List[Path], w: int, h: int, cache_dir: Path) -> bool:
    """
    Publish cache_dir/processed contents + manifest to tenant release asset as zip.
    """
    if not images_cache_enabled():
        print("  ⓘ Tenant images cache publish disabled (CACHE_RESET or ENABLE_TENANT_ASSETS_CACHE=false)")
        return False

    if not assets_enabled() or not gh_available():
        return False

    tenant_id = get_tenant_id()
    tag = get_tenant_assets_release_tag(tenant_id)
    asset = images_asset_name(tenant_id, w, h)

    manifest = _manifest_path(cache_dir, w, h)
    if not validate_local_manifest(manifest, source_images):
        # do not publish invalid cache
        return False

    composites_dir = _local_composites_dir(cache_dir)
    if not composites_dir.exists():
        return False

    try:
        ensure_release(tag, title=f"Tenant Assets {tenant_id}", notes="Persistent cache for preprocessed images & bundles.")
        tmp_zip = cache_dir / f"_{asset}"
        if tmp_zip.exists():
            tmp_zip.unlink()

        prefix = _zip_internal_prefix(tenant_id, w, h)
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            # include all files in processed (including manifest)
            for p in composites_dir.rglob("*"):
                # Avoid packaging temp download scratch (may exist after failed restores).
                if "_download_tmp" in p.parts:
                    continue
                if p.is_file():
                    arcname = prefix + p.relative_to(composites_dir).as_posix()
                    z.write(p, arcname)

        upload_asset(tag, tmp_zip, clobber=True)
        tmp_zip.unlink(missing_ok=True)
        print(f"  ✓ Published prepared images cache to tenant assets: {asset} (tag={tag})")
        return True
    except Exception as e:
        print(f"  ⚠ Failed to publish prepared images cache (non-fatal): {e}")
        return False