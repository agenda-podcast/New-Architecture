#!/usr/bin/env python3
"""
Release uploader for publishing podcast outputs to GitHub Releases.

Publishes all outputs for each topic to GitHub Releases under topic-scoped
folders with the following structure:

    {topic_id}/
      scripts/
        {topic_id}-{date}-{code}.script.txt
        {topic_id}-{date}-{code}.script.json
        {topic_id}-{date}-{code}.chapters.json
      audio/
        {topic_id}-{date}-{code}.m4a
      video/
        {topic_id}-{date}-{code}.mp4
      manifest.json

Features:
- Topic-scoped folder namespaces
- Idempotent uploads (version-bump or overwrite)
- Manifest with checksums and metadata
- Predictable asset paths
"""
import argparse
import hashlib
import zipfile
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from tenant_assets import ensure_release, upload_asset, delete_asset
from typing import Dict, List, Any, Optional

# Try to import subprocess for gh CLI usage
import subprocess


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


def upload_to_release(topic_id: str, output_dir: Path, date_str: str,
                     release_tag: Optional[str] = None,
                     dry_run: bool = False) -> bool:
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
    
    # Create manifest
    manifest = create_manifest(topic_id, output_dir, date_str)
    
    if not manifest['files']:
        print(f"No files found for {topic_id} on {date_str}")
        return False
    
    # Save manifest to output directory
    manifest_path = output_dir / 'manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    manifest['files'].append({
        'name': 'manifest.json',
        'size_bytes': manifest_path.stat().st_size,
        'checksum': compute_file_checksum(manifest_path),
        'type': 'json'
    })
    
    print(f"Manifest created with {len(manifest['files'])} files")
    
    # Group files by category
    files_by_category = {}
    for file_info in manifest['files']:
        filename = file_info['name']
        category = get_file_category(filename)
        if category not in files_by_category:
            files_by_category[category] = []
        files_by_category[category].append(filename)
    
    # Print summary
    print("\nFiles to upload:")
    for category, files in sorted(files_by_category.items()):
        print(f"  {category}/")
        for filename in files:
            file_path = output_dir / filename
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"    - {filename} ({size_mb:.2f} MB)")
    
    if dry_run:
        print("\nDry run - no files uploaded")
        return True
    
    # Check if gh CLI is available
    try:
        result = subprocess.run(['gh', '--version'], capture_output=True, timeout=5)
        if result.returncode != 0:
            print("ERROR: gh CLI not available")
            print("Install with: https://cli.github.com/")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("ERROR: gh CLI not found or not responding")
        return False
    
    # Check if release exists
    print(f"\nChecking if release {release_tag} exists...")
    result = subprocess.run(
        ['gh', 'release', 'view', release_tag],
        capture_output=True,
        text=True
    )
    
    release_exists = result.returncode == 0
    
    if release_exists:
        print(f"Release {release_tag} exists")
        # Delete old release to recreate with new files
        print(f"Deleting existing release {release_tag}...")
        result = subprocess.run(
            ['gh', 'release', 'delete', release_tag, '-y'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Warning: Failed to delete release: {result.stderr}")
    
    # Create new release
    print(f"Creating release {release_tag}...")
    release_title = f"{topic_id} - {date_str}"
    release_notes = f"Automated podcast generation for {topic_id} on {date_str}\n\n"
    release_notes += f"## Contents\n\n"
    for category, files in sorted(files_by_category.items()):
        release_notes += f"### {category.capitalize()}\n"
        for filename in files:
            release_notes += f"- `{filename}`\n"
        release_notes += "\n"
    
    result = subprocess.run(
        [
            'gh', 'release', 'create', release_tag,
            '--title', release_title,
            '--notes', release_notes
        ],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"ERROR: Failed to create release: {result.stderr}")
        return False
    
    print(f"✓ Release {release_tag} created")
    
    # Upload files with topic-scoped paths
    print("\nUploading files...")
    for file_info in manifest['files']:
        filename = file_info['name']
        file_path = output_dir / filename
        category = get_file_category(filename)
        
        # Note: GitHub doesn't support subdirectories in release assets
        # Files are uploaded with original names, organized via release notes
        
        print(f"  Uploading {filename} ({category})...")
        
        result = subprocess.run(
            ['gh', 'release', 'upload', release_tag, str(file_path),
             '--clobber'],  # Overwrite if exists
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"  ERROR: Failed to upload {filename}: {result.stderr}")
            return False
        
        print(f"  ✓ Uploaded {filename}")
    
    print(f"\n✓ Successfully uploaded {len(manifest['files'])} files to {release_tag}")
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
