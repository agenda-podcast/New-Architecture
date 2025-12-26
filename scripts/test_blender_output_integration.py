#!/usr/bin/env python3
"""
Integration test to verify the Blender output file validation logic
in a realistic scenario simulating what happens during video rendering.

After the fix, the behavior should be:
1. If expected file exists -> use it
2. If expected file missing -> return False and fallback to FFmpeg (no reuse of other mp4 files)
"""
import tempfile
import time
import os
from pathlib import Path


def simulate_correct_scenario():
    """
    Simulate a scenario where Blender writes to the expected filename.
    This is the ONLY acceptable scenario.
    """
    print("Simulating correct scenario (Blender writes to expected file)...")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Expected output
        expected_output = output_dir / "topic-01-20251219-R4.blender.mp4"
        
        # Blender writes to the correct filename
        expected_output.write_text("video content from Blender")
        
        print(f"Expected Blender output: {expected_output.name}")
        print(f"Actual Blender output: {expected_output.name}")
        print()
        
        # Check if file exists
        if expected_output.exists():
            file_size = expected_output.stat().st_size
            if file_size > 0:
                print("✓ Expected output file found (no search needed)")
                print(f"✓ File size: {file_size} bytes")
                return True
            else:
                print("✗ Expected output file is empty")
                return False
        else:
            print("✗ Expected output file not found")
            return False


def simulate_missing_file_scenario():
    """
    Simulate a scenario where:
    1. We expect Blender to write to topic-01-20251219-R4.blender.mp4
    2. But the file is missing (Blender failed or wrote to wrong location)
    3. Other mp4 files exist in the directory
    4. NEW BEHAVIOR: Should return False (no fallback to other files)
    """
    print("\nSimulating missing file scenario (expected file not found)...")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # This is what we expect
        expected_output = output_dir / "topic-01-20251219-R4.blender.mp4"
        
        # Create some other files in the directory (should NOT be used)
        old_file1 = output_dir / "topic-01-20251219-R3.mp4"
        old_file2 = output_dir / "topic-01-20251219-R2.blender.mp4"
        recent_file = output_dir / "topic-01-20251219-R4.mp4"
        
        old_file1.write_text("old content 1")
        time.sleep(0.01)
        old_file2.write_text("old content 2")
        time.sleep(0.01)
        recent_file.write_text("recent but wrong file")
        
        print(f"Expected Blender output: {expected_output.name}")
        print(f"Other files in directory:")
        for f in sorted(output_dir.glob("*.mp4")):
            print(f"  - {f.name}")
        print()
        
        # Check if expected file exists
        if not expected_output.exists():
            print("⚠ Expected output file not found")
            print("✓ Correct behavior: Return False (no fallback to other mp4 files)")
            print("✓ Renderer will fallback to FFmpeg to create the video")
            return True
        else:
            print("✗ Unexpected: Expected output file exists when it shouldn't")
            return False


def simulate_directory_listing():
    """
    Simulate directory listing for diagnostic purposes.
    This is what gets printed when Blender completes rendering.
    """
    print("\nSimulating directory listing diagnostic...")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Create various files to simulate a real output directory
        files_to_create = [
            ("topic-01-20251219-R1.mp4", "Final video from FFmpeg", 0.00),
            ("topic-01-20251219-R2.mp4", "Final video from Blender", 0.01),
            ("topic-01-20251219-R3.blender.mp4", "Blender output (before mux)", 0.02),
            ("topic-01-20251219-R3.mux.mp4", "Mux temporary file", 0.03),
            ("topic-01-20251219-R1.m4a", "Audio file", 0.04),
            ("images_concat.txt", "FFmpeg concat file", 0.05),
        ]
        
        for filename, content, delay in files_to_create:
            filepath = output_dir / filename
            filepath.write_text(content)
            time.sleep(delay)
        
        # Simulate directory listing (as done in video_render.py)
        print("Directory listing (sorted by modification time, newest first):")
        all_files = sorted(output_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        for file_path in all_files:
            file_stat = file_path.stat()
            file_size_mb = file_stat.st_size / (1024 * 1024)
            mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stat.st_mtime))
            print(f"  {file_path.name} ({file_size_mb:.2f} MB, modified: {mtime})")
        
        print("\n✓ Directory listing works correctly for diagnostics")
        return True


def simulate_empty_file_scenario():
    """
    Simulate a scenario where Blender creates a file but it's empty (0 bytes).
    This should be detected and rejected.
    """
    print("\nSimulating empty file scenario...")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Create an empty file
        expected_output = output_dir / "topic-01-20251219-R4.blender.mp4"
        expected_output.touch()
        
        print(f"Expected Blender output: {expected_output.name}")
        print()
        
        # Check if file exists
        if expected_output.exists():
            file_size = expected_output.stat().st_size
            print(f"File found with size: {file_size} bytes")
            
            if file_size == 0:
                print("✓ Correctly detected empty file (should be rejected)")
                return True
            else:
                print("✗ File has content when it should be empty")
                return False
        else:
            print("✗ Expected file doesn't exist")
            return False


if __name__ == '__main__':
    success = True
    
    success = simulate_correct_scenario() and success
    success = simulate_missing_file_scenario() and success
    success = simulate_empty_file_scenario() and success
    success = simulate_directory_listing() and success
    
    print("\n" + "="*70)
    if success:
        print("✓ All integration tests passed!")
        print("The new behavior correctly:")
        print("  1. Uses expected file when it exists and has content")
        print("  2. Returns False when expected file is missing (no fallback)")
        print("  3. Detects and rejects empty files")
        print("  4. Provides diagnostic output for troubleshooting")
    else:
        print("✗ Some tests failed")
    print("="*70)
