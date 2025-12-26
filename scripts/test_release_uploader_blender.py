#!/usr/bin/env python3
"""
Test for Blender video support in release_uploader.

Validates that:
1. .blender.mp4 files are included in manifest patterns
2. .blender.mp4 files are categorized as 'video'
3. Both .mp4 and .blender.mp4 files are properly handled
"""
import tempfile
import json
from pathlib import Path

try:
    from release_uploader import create_manifest, get_file_category, get_file_type
except ImportError as e:
    print(f"Error: Failed to import release_uploader module: {e}")
    print("Make sure you're running this from the scripts directory")
    import sys
    sys.exit(1)


def test_get_file_type():
    """Test that get_file_type correctly identifies file types including compound extensions."""
    print("Testing get_file_type()...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test Blender MP4 files
        blender_file = temp_path / 'topic-01-20251219-R1.blender.mp4'
        blender_file.touch()
        assert get_file_type(blender_file) == 'blender.mp4', \
            "Blender MP4 should have type 'blender.mp4'"
        print("  ✓ .blender.mp4 files have type 'blender.mp4'")
        
        # Test regular MP4 files
        regular_mp4 = temp_path / 'topic-01-20251219-L1.mp4'
        regular_mp4.touch()
        assert get_file_type(regular_mp4) == 'mp4', \
            "Regular MP4 should have type 'mp4'"
        print("  ✓ .mp4 files have type 'mp4'")
        
        # Test other file types
        m4a_file = temp_path / 'audio.m4a'
        m4a_file.touch()
        assert get_file_type(m4a_file) == 'm4a', \
            "M4A should have type 'm4a'"
        
        txt_file = temp_path / 'script.txt'
        txt_file.touch()
        assert get_file_type(txt_file) == 'txt', \
            "TXT should have type 'txt'"
        
        json_file = temp_path / 'sources.json'
        json_file.touch()
        assert get_file_type(json_file) == 'json', \
            "JSON should have type 'json'"
        
        # Test file without extension
        no_ext = temp_path / 'README'
        no_ext.touch()
        assert get_file_type(no_ext) == 'unknown', \
            "File without extension should have type 'unknown'"
        
        print("  ✓ Other file types correctly identified")


def test_get_file_category():
    """Test that get_file_category correctly identifies .blender.mp4 as video."""
    print("Testing get_file_category()...")
    
    # Test regular .mp4 files
    assert get_file_category('topic-01-20251219-R1.mp4') == 'video', \
        "Regular .mp4 should be categorized as 'video'"
    print("  ✓ Regular .mp4 files categorized as 'video'")
    
    # Test .blender.mp4 files
    assert get_file_category('topic-01-20251219-R1.blender.mp4') == 'video', \
        ".blender.mp4 should be categorized as 'video'"
    print("  ✓ .blender.mp4 files categorized as 'video'")
    
    # Test other file types still work correctly
    assert get_file_category('topic-01-20251219-R1.m4a') == 'audio', \
        ".m4a should be categorized as 'audio'"
    assert get_file_category('topic-01-20251219-R1.script.txt') == 'scripts', \
        ".script.txt should be categorized as 'scripts'"
    assert get_file_category('topic-01-20251219.sources.json') == 'metadata', \
        "sources.json should be categorized as 'metadata'"
    print("  ✓ Other file types still categorized correctly")


def test_create_manifest_includes_blender_videos():
    """Test that create_manifest includes .blender.mp4 files in the manifest."""
    print("\nTesting create_manifest() includes .blender.mp4 files...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        topic_id = "topic-01"
        date_str = "20251219"
        
        # Create test files (both .mp4 and .blender.mp4)
        test_files = [
            f"{topic_id}-{date_str}-L1.mp4",
            f"{topic_id}-{date_str}-R1.blender.mp4",
            f"{topic_id}-{date_str}-M2.blender.mp4",
            f"{topic_id}-{date_str}-L1.m4a",
            f"{topic_id}-{date_str}-L1.script.txt",
            f"{topic_id}-{date_str}.sources.json",
        ]
        
        for filename in test_files:
            file_path = output_dir / filename
            file_path.write_text(f"test content for {filename}")
        
        # Create manifest
        manifest = create_manifest(topic_id, output_dir, date_str)
        
        # Verify manifest includes all files
        manifest_filenames = [f['name'] for f in manifest['files']]
        
        print(f"  Created manifest with {len(manifest_filenames)} files:")
        for filename in sorted(manifest_filenames):
            print(f"    - {filename}")
        
        # Check that .blender.mp4 files are included
        assert f"{topic_id}-{date_str}-R1.blender.mp4" in manifest_filenames, \
            "R1.blender.mp4 should be in manifest"
        assert f"{topic_id}-{date_str}-M2.blender.mp4" in manifest_filenames, \
            "M2.blender.mp4 should be in manifest"
        print("  ✓ .blender.mp4 files included in manifest")
        
        # Check that regular .mp4 files are still included
        assert f"{topic_id}-{date_str}-L1.mp4" in manifest_filenames, \
            "Regular .mp4 should still be in manifest"
        print("  ✓ Regular .mp4 files still included in manifest")
        
        # Verify file count (should have all 6 test files)
        assert len(manifest_filenames) == 6, \
            f"Expected 6 files in manifest, got {len(manifest_filenames)}"
        print(f"  ✓ All {len(test_files)} files included in manifest")


def test_blender_and_regular_mp4_coexist():
    """Test that both .mp4 and .blender.mp4 files for the same content can coexist."""
    print("\nTesting coexistence of .mp4 and .blender.mp4 files...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        topic_id = "topic-01"
        date_str = "20251219"
        
        # Create both .mp4 and .blender.mp4 for the same content
        test_files = [
            f"{topic_id}-{date_str}-R1.mp4",
            f"{topic_id}-{date_str}-R1.blender.mp4",
        ]
        
        for filename in test_files:
            file_path = output_dir / filename
            file_path.write_text(f"test content for {filename}")
        
        # Create manifest
        manifest = create_manifest(topic_id, output_dir, date_str)
        
        # Verify both are included
        manifest_filenames = [f['name'] for f in manifest['files']]
        
        assert f"{topic_id}-{date_str}-R1.mp4" in manifest_filenames, \
            "Regular .mp4 should be included"
        assert f"{topic_id}-{date_str}-R1.blender.mp4" in manifest_filenames, \
            ".blender.mp4 should be included"
        
        print(f"  ✓ Both .mp4 and .blender.mp4 files can coexist in manifest")
        print(f"    Files in manifest: {manifest_filenames}")


def test_manifest_file_metadata():
    """Test that .blender.mp4 files have proper metadata in manifest."""
    print("\nTesting .blender.mp4 file metadata in manifest...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        topic_id = "topic-01"
        date_str = "20251219"
        
        # Create both a .blender.mp4 file and a regular .mp4 file
        test_content = "test video content " * 100
        blender_file = output_dir / f"{topic_id}-{date_str}-R1.blender.mp4"
        blender_file.write_text(test_content)
        
        regular_mp4_file = output_dir / f"{topic_id}-{date_str}-L1.mp4"
        regular_mp4_file.write_text(test_content)
        
        # Create manifest
        manifest = create_manifest(topic_id, output_dir, date_str)
        
        # Find the blender.mp4 entry
        blender_entry = None
        regular_mp4_entry = None
        for file_info in manifest['files']:
            if file_info['name'] == f"{topic_id}-{date_str}-R1.blender.mp4":
                blender_entry = file_info
            elif file_info['name'] == f"{topic_id}-{date_str}-L1.mp4":
                regular_mp4_entry = file_info
        
        assert blender_entry is not None, ".blender.mp4 file should be in manifest"
        assert regular_mp4_entry is not None, "Regular .mp4 file should be in manifest"
        
        # Verify blender.mp4 metadata
        assert 'size_bytes' in blender_entry, "File should have size_bytes"
        assert blender_entry['size_bytes'] == len(test_content), \
            f"Size should match: expected {len(test_content)}, got {blender_entry['size_bytes']}"
        
        assert 'checksum' in blender_entry, "File should have checksum"
        assert len(blender_entry['checksum']) == 64, "Checksum should be SHA256 (64 chars)"
        
        assert 'type' in blender_entry, "File should have type"
        assert blender_entry['type'] == 'blender.mp4', "Blender file type should be 'blender.mp4'"
        
        # Verify regular .mp4 has different type
        assert 'type' in regular_mp4_entry, "Regular mp4 should have type"
        assert regular_mp4_entry['type'] == 'mp4', "Regular mp4 type should be 'mp4'"
        
        print(f"  ✓ .blender.mp4 file has proper metadata:")
        print(f"    - size_bytes: {blender_entry['size_bytes']}")
        print(f"    - checksum: {blender_entry['checksum'][:16]}...")
        print(f"    - type: {blender_entry['type']}")
        print(f"  ✓ Regular .mp4 file has different type:")
        print(f"    - type: {regular_mp4_entry['type']}")


def main():
    """Run all tests."""
    print("="*60)
    print("Release Uploader Blender Support Tests")
    print("="*60)
    
    try:
        test_get_file_type()
        test_get_file_category()
        test_create_manifest_includes_blender_videos()
        test_blender_and_regular_mp4_coexist()
        test_manifest_file_metadata()
        
        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
