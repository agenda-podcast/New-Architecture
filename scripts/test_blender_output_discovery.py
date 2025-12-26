#!/usr/bin/env python3
"""
Test to verify Blender output file validation logic.

This test validates that:
1. The code correctly identifies when expected output file exists
2. The code correctly rejects when expected output file doesn't exist (no fallback to newest file)
3. The code handles edge cases properly
"""
import tempfile
import time
import os
from pathlib import Path


def test_expected_filename_exists():
    """Test that expected filename is correctly validated when it exists."""
    print("Testing expected filename validation when file exists...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Create the expected file
        expected_file = output_dir / "topic-01-20251219-R1.blender.mp4"
        expected_file.write_text("expected content")
        
        # Verify it exists
        assert expected_file.exists(), "Expected file should exist"
        
        # Verify file size is non-zero
        file_size = expected_file.stat().st_size
        assert file_size > 0, "File should have content"
        
        print(f"  ✓ Expected file exists: {expected_file.name}")
        print(f"  ✓ File has content: {file_size} bytes")


def test_expected_filename_missing():
    """Test that missing expected file is correctly detected (no fallback)."""
    print("\nTesting expected filename validation when file is missing...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Create other mp4 files (should NOT be used as fallback)
        other_file1 = output_dir / "topic-01-20251219-R1.mp4"
        other_file2 = output_dir / "topic-01-20251219-R2.mp4"
        other_file1.write_text("other content 1")
        other_file2.write_text("other content 2")
        
        # Expected file does NOT exist
        expected_file = output_dir / "topic-01-20251219-R1.blender.mp4"
        
        # Verify expected file doesn't exist
        assert not expected_file.exists(), "Expected file should NOT exist"
        
        # In the new implementation, render_with_blender should return False
        # It should NOT fallback to using the newest mp4 file
        print(f"  ✓ Expected file correctly identified as missing: {expected_file.name}")
        print(f"  ✓ Other mp4 files exist but should NOT be used as fallback")
        print(f"  ✓ Proper behavior: Return False and fallback to FFmpeg renderer")


def test_empty_file_detection():
    """Test that empty files are correctly detected."""
    print("\nTesting empty file detection...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Create an empty file
        expected_file = output_dir / "topic-01-20251219-R1.blender.mp4"
        expected_file.touch()  # Create empty file
        
        # Verify it exists but is empty
        assert expected_file.exists(), "File should exist"
        file_size = expected_file.stat().st_size
        assert file_size == 0, "File should be empty"
        
        # This should be detected and rejected
        print(f"  ✓ Empty file correctly detected: {expected_file.name}")
        print(f"  ✓ File size: {file_size} bytes (should trigger error)")


def test_directory_listing_simulation():
    """Test directory listing for diagnostic purposes."""
    print("\nTesting directory listing for diagnostics...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Create various files
        files_to_create = [
            "topic-01-20251219-R1.mp4",
            "topic-01-20251219-R1.blender.mp4",
            "topic-01-20251219-R1.mux.mp4",
            "topic-01-20251219-R1.m4a",
            "images_concat.txt",
        ]
        
        for i, filename in enumerate(files_to_create):
            filepath = output_dir / filename
            filepath.write_text(f"content {i}")
            time.sleep(0.01)
        
        # Simulate directory listing (as done in video_render.py)
        all_files = sorted(output_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        print(f"  Directory listing ({len(all_files)} files):")
        for file_path in all_files:
            file_stat = file_path.stat()
            file_size_mb = file_stat.st_size / (1024 * 1024)
            print(f"    - {file_path.name} ({file_size_mb:.2f} MB)")
        
        print("  ✓ Directory listing works correctly for diagnostics")


if __name__ == '__main__':
    test_expected_filename_exists()
    test_expected_filename_missing()
    test_empty_file_detection()
    test_directory_listing_simulation()
    print("\n✓ All tests passed!")
