#!/usr/bin/env python3
"""scripts/release_uploader.py

GitHub Releases uploader.

**Policy (as requested):**
- A release must contain **ONLY** the final burned videos.
- Assets must be **flat** (GitHub Releases are flat by design).
- Asset names must be **clean**: no tenant, no date, no folders.

Operational behavior:
- Deletes ALL existing assets in the target release tag.
- Uploads only final MP4(s) discovered in the topic output directory.

Naming:
- topic-01-20251229-R8.mp4            -> R8.mp4
- topic-01-20251229-R1.blender.mp4    -> R1.mp4
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from tenant_assets import ensure_release, upload_asset, delete_asset
from typing import Dict, List, Any, Optional

# Try to import subprocess for gh CLI usage
import subprocess


def _run_gh(cmd: list[str]) -> tuple[int, str, str]:
    """Run a gh CLI command and return (rc, stdout, stderr)."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def list_release_assets(tag: str) -> List[str]:
    """Return a list of asset names for a release tag."""
    rc, out, err = _run_gh(["gh", "release", "view", tag, "--json", "assets", "--jq", ".assets[].name"])
    if rc != 0:
        # If release doesn't exist yet, treat as empty.
        if "release not found" in (err or "").lower():
            return []
        raise RuntimeError(f"Failed to list assets for {tag}: {err or out}")
    assets = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return assets


def _extract_code_from_filename(name: str) -> Optional[str]:
    """Extract content code (e.g., R8, M1, S2) from expected output filenames."""
    base = name
    if base.endswith(".blender.mp4"):
        base = base[: -len(".blender.mp4")]
    elif base.endswith(".mp4"):
        base = base[: -len(".mp4")]
    parts = base.split("-")
    if not parts:
        return None
    code = parts[-1].strip()
    if not code:
        return None
    return code


def find_final_videos(topic_id: str, output_dir: Path, date_str: str) -> List[Path]:
    """Find final video files for a topic/date.

    Prefers non-blender .mp4 if both exist for the same code.
    """
    cand: List[Path] = []
    # Collect both types
    cand += sorted(output_dir.glob(f"{topic_id}-{date_str}-*.mp4"))
    cand += sorted(output_dir.glob(f"{topic_id}-{date_str}-*.blender.mp4"))

    # De-duplicate per code, prefer plain .mp4
    by_code: Dict[str, Path] = {}
    for p in cand:
        if not p.is_file():
            continue
        code = _extract_code_from_filename(p.name)
        if not code:
            continue
        prev = by_code.get(code)
        if prev is None:
            by_code[code] = p
            continue
        # Prefer non-blender mp4
        if prev.name.endswith(".blender.mp4") and p.name.endswith(".mp4"):
            by_code[code] = p

    # Stable order by code
    return [by_code[k] for k in sorted(by_code.keys())]


def compute_file_checksum(file_path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def count_words_in_file(file_path: Path) -> int:
    """Count words in a text file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return len(content.split())
    except Exception:
        return 0


def get_file_type(file_path: Path) -> str:
    """
    Determine file type from filename.
    
    Handles compound extensions like .blender.mp4 specifically to distinguish
    Blender-rendered videos from regular MP4 videos in the manifest.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File type string (e.g., 'mp4', 'blender.mp4', 'm4a', 'txt', etc.)
    """
    filename = file_path.name
    
    # Check for compound extensions first (most specific)
    if filename.endswith('.blender.mp4'):
        return 'blender.mp4'
    
    # Fall back to regular suffix
    if file_path.suffix:
        return file_path.suffix[1:]  # Remove leading dot
    
    return 'unknown'


def create_manifest(topic_id: str, output_dir: Path, date_str: str) -> Dict[str, Any]:
    """
    Create manifest with metadata for all outputs.
    
    Args:
        topic_id: Topic identifier
        output_dir: Directory containing topic outputs
        date_str: Date string (YYYYMMDD)
        
    Returns:
        Manifest dictionary
    """
    manifest = {
        'topic_id': topic_id,
        'date': date_str,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'files': []
    }
    
    # Find all output files
    patterns = [
        f"{topic_id}-{date_str}-*.script.txt",
        f"{topic_id}-{date_str}-*.script.json",
        f"{topic_id}-{date_str}-*.chapters.json",
        f"{topic_id}-{date_str}-*.m4a",
        f"{topic_id}-{date_str}-*.mp4",
        f"{topic_id}-{date_str}-*.blender.mp4",
        f"{topic_id}-{date_str}.sources.json"
    ]
    
    # Track files already added to avoid duplicates
    # (*.mp4 pattern matches *.blender.mp4 files since they end with .mp4)
    # Using filename is safe since all patterns search in the same flat directory (output_dir)
    seen_files = set()
    
    for pattern in patterns:
        for file_path in output_dir.glob(pattern):
            if file_path.is_file() and file_path.name not in seen_files:
                seen_files.add(file_path.name)
                
                file_info = {
                    'name': file_path.name,
                    'size_bytes': file_path.stat().st_size,
                    'checksum': compute_file_checksum(file_path),
                    'type': get_file_type(file_path)
                }
                
                # Add word count for text files
                if file_path.suffix == '.txt':
                    file_info['word_count'] = count_words_in_file(file_path)
                
                manifest['files'].append(file_info)
    
    return manifest


def get_file_category(filename: str) -> str:
    """Determine category for a file based on its name."""
    if '.script.' in filename or '.chapters.' in filename:
        return 'scripts'
    elif filename.endswith('.m4a'):
        return 'audio'
    elif filename.endswith('.mp4') or filename.endswith('.blender.mp4'):
        return 'video'
    elif filename.endswith('.json') and 'sources' in filename:
        return 'metadata'
    else:
        return 'other'


def upload_to_release(
    topic_id: str,
    output_dir: Path,
    date_str: str,
    release_tag: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """
    Upload topic outputs to GitHub Release.
    
    Args:
        topic_id: Topic identifier
        output_dir: Directory containing topic outputs
        date_str: Date string (YYYYMMDD)
        release_tag: Release tag (default: {topic_id}-latest)
        dry_run: If True, show what would be uploaded without uploading
        
    Returns:
        True if successful, False otherwise
    """
    if release_tag is None:
        release_tag = f"{topic_id}-latest"
    
    print(f"Preparing release for {topic_id} (tag: {release_tag})")

    videos = find_final_videos(topic_id, output_dir, date_str)
    if not videos:
        print(f"No final videos found for {topic_id} on {date_str}")
        return False

    print("\nVideos to upload (final only):")
    for p in videos:
        size_mb = p.stat().st_size / (1024 * 1024)
        code = _extract_code_from_filename(p.name) or p.stem
        print(f"  - {p.name} -> {code}.mp4 ({size_mb:.2f} MB)")
    
    if dry_run:
        print("\nDry run - no files uploaded")
        return True
    
    # Ensure release exists
    # Hard reset the release so ONLY the desired video assets are present.
    # This protects against other jobs that previously uploaded zips/folders.
    reset = os.getenv("RESET_RELEASE", "1").strip().lower() in ("1", "true", "yes", "y", "on")
    if reset:
        rc, _, err = _run_gh(["gh", "release", "delete", release_tag, "-y"])
        if rc == 0:
            print(f"  ✓ Deleted existing release tag={release_tag} (reset)")
        else:
            # Non-fatal: tag may not exist yet.
            if "release not found" not in (err or "").lower():
                print(f"  ⓘ Could not delete release (may not exist): {err}")

    ensure_release(release_tag, title=f"{topic_id} videos")

    # Delete ALL existing assets so the release contains ONLY final videos.
    # (Useful even when reset is off.)
    existing = list_release_assets(release_tag)
    if existing:
        print(f"\nCleaning existing release assets ({len(existing)}):")
        for a in existing:
            print(f"  - deleting: {a}")
            if not dry_run:
                delete_asset(release_tag, a)

    # Upload videos with clean names (no tenant/date/topic).
    tmp_dir = output_dir / "_release_tmp"
    if not dry_run:
        tmp_dir.mkdir(parents=True, exist_ok=True)

    uploaded = 0
    for p in videos:
        code = _extract_code_from_filename(p.name) or p.stem
        asset_name = f"{code}.mp4"

        if dry_run:
            print(f"  (dry) upload: {p.name} as {asset_name}")
            continue

        staged = tmp_dir / asset_name
        try:
            # Copy to enforce the desired asset name.
            import shutil

            shutil.copy2(p, staged)
            upload_asset(release_tag, staged, clobber=True)
            uploaded += 1
        finally:
            try:
                if staged.exists():
                    staged.unlink()
            except Exception:
                pass

    # Cleanup tmp dir (best-effort)
    if not dry_run:
        try:
            if tmp_dir.exists():
                tmp_dir.rmdir()
        except Exception:
            pass

    print(f"\nUploaded {uploaded} video asset(s) to {release_tag}")
    return True



def _env_bool(name: str, default: bool = True) -> bool:
    v = os.environ.get(name, str(default)).strip().lower()
    return v not in ("0", "false", "no", "off")


def _tenant_id() -> str:
    return os.environ.get("TENANT_ID", "0000000001").strip() or "0000000001"


def _tenant_assets_tag() -> str:
    tid = _tenant_id()
    return os.environ.get("TENANT_ASSETS_RELEASE_TAG", f"tenant-assets-{tid}")


def _zip_write(z: zipfile.ZipFile, src: Path, arc: str) -> None:
    z.write(src, arcname=arc)


def _iter_outputs_for_topic_date(topic_id: str, output_dir: Path, date_str: str) -> List[Path]:
    """Collect output files for a given {topic,date} in output_dir."""
    candidates: List[Path] = []

    # Most artifacts follow: <topic>-<date>-R#.ext
    for p in output_dir.glob(f"{topic_id}-{date_str}-*.*"):
        if p.is_file():
            candidates.append(p)

    # Include shared metadata/manifest if present
    for extra in [output_dir / f"{topic_id}-{date_str}.sources.json", output_dir / "manifest.json"]:
        if extra.exists() and extra.is_file():
            candidates.append(extra)

    # De-dup while preserving stable ordering
    by_name = {p.name: p for p in candidates}
    return [by_name[n] for n in sorted(by_name.keys())]


def build_outputs_type_zips(
    topic_id: str,
    output_dir: Path,
    date_str: str,
    zip_dir: Path,
) -> Dict[str, Path]:
    """
    Build one ZIP per output type (as requested):
      - Text (.txt)
      - JSON (.json)
      - Subtitles (.srt)
      - Audio (.m4a, .mp3, .wav)
      - Video (.mp4, .mov)

    Each ZIP contains a tenant-scoped folder hierarchy inside the archive:
      Assets/<TENANT_ID>/Outputs/<topic>/<date>/<Type>/...

    Returns a dict: {"text": Path, "json": Path, ...} for zips that were created.
    """
    tid = _tenant_id()
    base = f"Assets/{tid}/Outputs/{topic_id}/{date_str}/"

    def _type_for_file(p: Path) -> Optional[str]:
        name = p.name.lower()
        suf = p.suffix.lower()

        if suf == ".srt" or name.endswith(".captions.srt"):
            return "subtitles"
        if suf in (".m4a", ".mp3", ".wav"):
            return "audio"
        if suf in (".mp4", ".mov"):
            return "video"
        if suf == ".json":
            return "json"
        if suf == ".txt":
            return "text"
        return None

    type_labels = {
        "text": "Text",
        "json": "JSON",
        "subtitles": "Subtitles",
        "audio": "Audio",
        "video": "Video",
    }

    files = _iter_outputs_for_topic_date(topic_id, output_dir, date_str)
    buckets: Dict[str, List[Path]] = {k: [] for k in type_labels.keys()}
    for p in files:
        t = _type_for_file(p)
        if t:
            buckets[t].append(p)

    created: Dict[str, Path] = {}
    zip_dir.mkdir(parents=True, exist_ok=True)

    for t, plist in buckets.items():
        if not plist:
            continue
        zip_name = f"Assets_{tid}_{type_labels[t]}_{topic_id}_{date_str}.zip"
        zip_path = zip_dir / zip_name
        if zip_path.exists():
            zip_path.unlink()

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for p in sorted(plist, key=lambda x: x.name):
                arc = f"{base}{type_labels[t]}/{p.name}"
                _zip_write(z, p, arc)

        created[t] = zip_path

    return created


def build_images_cache_zip(output_dir: Path, w: int, h: int, zip_path: Path) -> bool:
    """
    Package _prepared_images/<WxH>/processed into a ZIP:
      Assets/<TENANT_ID>/Images/<WxH>/processed/...
    Returns True if built, False if cache not present.
    """
    tid = _tenant_id()
    cache_dir = output_dir / "_prepared_images" / f"{w}x{h}" / "processed"
    if not cache_dir.exists():
        return False
    base = f"Assets/{tid}/Images/{w}x{h}/processed/"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in cache_dir.rglob("*"):
            if p.is_file():
                arc = base + p.relative_to(cache_dir).as_posix()
                _zip_write(z, p, arc)
    return True


def upload_tenant_assets(topic_id: str, output_dir: Path, date_str: str, topic_release_tag: str) -> None:
    """
    Upload tenant-structured ZIP bundles to:
      - the topic release (for visibility per run)
      - the persistent tenant assets release (for caching & organization)

    Note: the folder hierarchy is inside the ZIP. GitHub Release assets are flat.
    """
    if not _env_bool("ENABLE_TENANT_ASSETS", True):
        return

    tid = _tenant_id()
    tenant_tag = _tenant_assets_tag()
    ensure_release(tenant_tag, title=f"Tenant Assets {tid}", notes="Persistent cache + organized bundles.")

    # Clean up legacy combined bundle (previous design) to avoid confusion.
    legacy_name = f"Assets_{tid}_Outputs_{topic_id}_{date_str}.zip"
    delete_asset(tenant_tag, legacy_name)
    # Topic release is recreated frequently; still best-effort remove if present.
    delete_asset(topic_release_tag, legacy_name)

    # Outputs: one ZIP per output type (Text/Json/Subtitles/Audio/Video)
    zips_by_type = build_outputs_type_zips(topic_id, output_dir, date_str, zip_dir=output_dir)

    # Upload to tenant release; optionally also to topic release if desired
    upload_to_topic = _env_bool("UPLOAD_OUTPUT_TYPE_ZIPS_TO_TOPIC_RELEASE", False)
    for t, zp in zips_by_type.items():
        try:
            upload_asset(tenant_tag, zp, clobber=True)
            print(f"  ✓ Uploaded tenant outputs ZIP ({t}) to tenant release: {zp.name} (tag={tenant_tag})")
        except Exception as e:
            print(f"  ⚠ Failed to upload tenant outputs ZIP ({t}) to tenant release (non-fatal): {e}")

        if upload_to_topic:
            try:
                upload_asset(topic_release_tag, zp, clobber=True)
                print(f"  ✓ Uploaded tenant outputs ZIP ({t}) to topic release: {zp.name}")
            except Exception as e:
                print(f"  ⚠ Failed to upload tenant outputs ZIP ({t}) to topic release (non-fatal): {e}")

    # Images cache bundle(s) if present for common resolutions
    for w, h in [(1080, 1920), (1920, 1080)]:
        img_zip_name = f"Assets_{tid}_Images_{w}x{h}.zip"
        img_zip_path = output_dir / img_zip_name
        built = build_images_cache_zip(output_dir, w, h, img_zip_path)
        if not built:
            continue
        try:
            upload_asset(tenant_tag, img_zip_path, clobber=True)
            print(f"  ✓ Uploaded images cache to tenant release: {img_zip_name} (tag={tenant_tag})")
        except Exception as e:
            print(f"  ⚠ Failed to upload images cache to tenant release (non-fatal): {e}")
        # Keep topic release less noisy by default; enable explicitly if desired
        if _env_bool("UPLOAD_IMAGES_CACHE_TO_TOPIC_RELEASE", False):
            try:
                upload_asset(topic_release_tag, img_zip_path, clobber=True)
                print(f"  ✓ Uploaded images cache to topic release: {img_zip_name}")
            except Exception as e:
                print(f"  ⚠ Failed to upload images cache to topic release (non-fatal): {e}")

    # Cleanup local zips
    for zp in zips_by_type.values():
        try:
            zp.unlink(missing_ok=True)
        except Exception:
            pass
    for p in output_dir.glob(f"Assets_{tid}_Images_*x*.zip"):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Upload podcast outputs to GitHub Releases'
    )
    parser.add_argument('--topic', required=True, help='Topic ID (e.g., topic-01)')
    parser.add_argument('--date', help='Date string (YYYYMMDD, default: today)')
    parser.add_argument('--output-dir', help='Output directory (default: outputs/{topic})')
    parser.add_argument('--release-tag', help='Release tag (default: {topic}-latest)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    
    args = parser.parse_args()
    
    # Determine date
    date_str = args.date or datetime.now().strftime('%Y%m%d')
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        # Default to outputs/{topic}/
        repo_root = Path(__file__).parent.parent
        output_dir = repo_root / 'outputs' / args.topic
    
    if not output_dir.exists():
        print(f"ERROR: Output directory does not exist: {output_dir}")
        return 1
    
    # Upload to release
    success = upload_to_release(
        topic_id=args.topic,
        output_dir=output_dir,
        date_str=date_str,
        release_tag=args.release_tag,
        dry_run=args.dry_run
    )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
