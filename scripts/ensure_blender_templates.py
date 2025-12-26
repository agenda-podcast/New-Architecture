#!/usr/bin/env python3
"""
Blender Templates Verification and Download Script

This script ensures that all Blender template files specified in templates/inventory.yml
are present on disk. If templates are missing, it can automatically download and extract
them from a bundle URL.

Features:
- Skips non-selectable templates (e.g., base templates with selectable: false)
- Optional preview image validation (use --require-previews)
- Safe ZIP extraction to prevent path traversal attacks
- Clear error messages for missing configuration

Usage:
    # Basic verification (previews optional, non-selectable templates skipped)
    python3 scripts/ensure_blender_templates.py
    
    # Fail if templates are missing and cannot be downloaded
    python3 scripts/ensure_blender_templates.py --required
    
    # Require preview images to be present
    python3 scripts/ensure_blender_templates.py --require-previews
    
    # Provide custom bundle URL
    python3 scripts/ensure_blender_templates.py --bundle-url https://example.com/templates.zip
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import zipfile
from pathlib import Path
from typing import Dict, Any, List

import yaml
import urllib.request


def load_inventory(inventory_path: Path) -> Dict[str, Any]:
    """
    Load template inventory from YAML file.
    
    Args:
        inventory_path: Path to inventory.yml file
        
    Returns:
        Inventory dictionary
        
    Raises:
        ValueError: If inventory file doesn't parse into a dict
    """
    data = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("inventory.yml did not parse into a dict")
    return data


def expected_files(repo_root: Path, inventory: Dict[str, Any], require_previews: bool = False) -> List[Path]:
    """
    Extract list of expected template files from inventory.
    
    Args:
        repo_root: Repository root directory
        inventory: Inventory dictionary from load_inventory()
        require_previews: If True, preview files are required; if False, they are optional
        
    Returns:
        List of expected file paths (deduplicated)
    """
    files: List[Path] = []
    for template_id, meta in inventory.items():
        if not isinstance(meta, dict):
            continue
        
        # Skip non-selectable templates (e.g., base template)
        if not meta.get("selectable", True):
            continue
        
        rel = meta.get("path")
        if rel and str(rel).endswith(".blend"):
            files.append(repo_root / rel)

        # Include preview files only if required
        if require_previews:
            preview = meta.get("preview")
            if preview:
                files.append(repo_root / preview)

    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for p in files:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def check_missing(files: List[Path]) -> List[Path]:
    """
    Check which files from the list are missing.
    
    Args:
        files: List of file paths to check
        
    Returns:
        List of missing file paths
    """
    return [p for p in files if not p.exists()]


def is_safe_path(base_path: Path, target_path: Path) -> bool:
    """
    Check if target path is safe (no path traversal).
    
    Args:
        base_path: Base directory for extraction
        target_path: Target path to validate
        
    Returns:
        True if path is safe to extract
    """
    try:
        # Resolve both paths to absolute, normalized paths
        base = base_path.resolve()
        target = target_path.resolve()
        
        # Check if target is within base directory
        try:
            # Python 3.9+ has is_relative_to - most reliable method
            return target.is_relative_to(base)
        except AttributeError:
            # Fallback for older Python versions
            # Use commonpath for robust containment check
            try:
                common = Path(os.path.commonpath([str(base), str(target)]))
                return common == base
            except ValueError:
                # Paths are on different drives (Windows) or one is relative
                return False
    except (ValueError, OSError):
        return False


def download_and_extract_zip(url: str, dest_root: Path) -> None:
    """
    Download and extract a ZIP bundle to the destination directory with security checks.
    
    Implements safe extraction to prevent path traversal attacks (Zip Slip).
    
    Args:
        url: URL to download ZIP from
        dest_root: Root directory to extract files into
        
    Raises:
        ValueError: If ZIP contains unsafe paths
        Various exceptions from urllib or zipfile on failure
    """
    print(f"Downloading Blender templates bundle: {url}")
    
    # Create request with timeout for security
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=300) as resp:
        data = resp.read()

    print(f"Downloaded {len(data)/1e6:.2f} MB. Extracting...")
    
    # Safe extraction with path validation
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.namelist():
            # Normalize the path to handle different separators and clean up redundant parts
            normalized_member = os.path.normpath(member)
            
            # Skip absolute paths (handles paths starting with separators too)
            if os.path.isabs(normalized_member):
                print(f"Skipping absolute path in ZIP: {member}")
                continue
            
            # Skip paths that try to escape using ..
            # Use Path.parts for cross-platform separator handling
            member_parts = Path(normalized_member).parts
            if '..' in member_parts:
                print(f"Skipping path with '..' in ZIP: {member}")
                continue
            
            # Validate the final extraction path
            member_path = dest_root / normalized_member
            if not is_safe_path(dest_root, member_path):
                raise ValueError(f"Unsafe path in ZIP archive: {member}")
            
            # Extract this member
            zf.extract(member, dest_root)

    print("Extraction complete.")


def main() -> int:
    """
    Main entry point for template verification and download.
    
    Returns:
        Exit code (0 = success, non-zero = error)
    """
    ap = argparse.ArgumentParser(
        description="Verify and download Blender templates"
    )
    ap.add_argument("--repo-root", default=".", help="Repo root directory")
    ap.add_argument("--inventory", default="templates/inventory.yml", help="Path to inventory.yml")
    ap.add_argument("--bundle-url", default=os.getenv("BLENDER_TEMPLATES_BUNDLE_URL", ""), help="Zip bundle URL")
    ap.add_argument("--required", action="store_true", help="Fail if templates are missing and cannot be downloaded")
    ap.add_argument("--require-previews", action="store_true", help="Require preview images (default: previews are optional)")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    inventory_path = (repo_root / args.inventory).resolve()

    if not inventory_path.exists():
        print(f"ERROR: inventory not found: {inventory_path}")
        return 1

    inv = load_inventory(inventory_path)
    files = expected_files(repo_root, inv, require_previews=args.require_previews)
    missing = check_missing(files)

    if not missing:
        print(f"✓ Blender templates present: {len(files)} files verified")
        return 0

    print(f"⚠ Missing {len(missing)} template file(s). Examples:")
    for p in missing[:10]:
        print(f"  - {p.relative_to(repo_root)}")
    if len(missing) > 10:
        print(f"  ... and {len(missing) - 10} more")

    if not args.bundle_url:
        msg = "BLENDER_TEMPLATES_BUNDLE_URL not set; cannot download templates."
        if args.required:
            print(f"\nERROR: {msg}")
            print("\nTo fix this issue:")
            print("  1. Set BLENDER_TEMPLATES_BUNDLE_URL as a repository or environment secret in GitHub")
            print("  2. Or provide --bundle-url with a valid template bundle URL")
            print("\nFor GitHub Actions, configure the secret at:")
            print("  Settings → Secrets and variables → Actions → Repository secrets")
            print("  OR")
            print("  Settings → Environments → [Your Environment] → Secrets")
            return 2
        print(f"WARNING: {msg} Proceeding without templates.")
        return 0

    download_and_extract_zip(args.bundle_url, repo_root)

    # Recheck
    missing2 = check_missing(files)
    if missing2:
        print("\nERROR: Templates download/extract completed, but some files are still missing.")
        print("\nThis could indicate:")
        print("  - The ZIP bundle does not contain all expected templates")
        print("  - The ZIP bundle has a different directory structure than expected")
        print("\nMissing files:")
        for p in missing2[:20]:
            print(f"  - {p.relative_to(repo_root)}")
        if len(missing2) > 20:
            print(f"  ... and {len(missing2) - 20} more")
        return 3

    print("✓ Blender templates installed and verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
