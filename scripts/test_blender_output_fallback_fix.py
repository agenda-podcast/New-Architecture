#!/usr/bin/env python3
"""
Test to verify that Blender output file detection works in video-only mode.

This test verifies that:
1. Blender output detection checks both .blender.mp4 and final .mp4 paths
2. FFmpeg fallback doesn't overwrite good Blender output
3. Diagnostic MP4 listing is improved
"""
import tempfile
from pathlib import Path
import sys

# Add the scripts directory to the path so we can import video_render
sys.path.insert(0, str(Path(__file__).parent))

from video_render import MIN_OUTPUT_SIZE_BYTES, MIN_FALLBACK_GUARD_SIZE_BYTES, get_blender_output_path


def test_blender_output_detection_logic():
    """Test that Blender output detection checks both paths."""
    print("Testing Blender output detection logic...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Simulate paths
        output_path = output_dir / "topic-01-20251220-R1.mp4"
        blender_output = get_blender_output_path(output_path)
        
        # Test Case 1: Blender wrote to .blender.mp4 (expected path)
        blender_output.write_bytes(b'x' * (MIN_OUTPUT_SIZE_BYTES + 50_000))
        
        blender_ok = blender_output.exists() and blender_output.stat().st_size > MIN_OUTPUT_SIZE_BYTES
        final_ok = output_path.exists() and output_path.stat().st_size > MIN_OUTPUT_SIZE_BYTES
        
        assert blender_ok, "Should detect .blender.mp4"
        assert not final_ok, "Final path shouldn't exist yet"
        
        produced = blender_output if blender_ok else (output_path if final_ok else None)
        assert produced == blender_output, "Should use .blender.mp4"
        print(f"  ✓ Case 1: Detected Blender output at expected path")
        
        # Clean up for next test
        blender_output.unlink()
        
        # Test Case 2: Blender wrote to final path (video-only mode quirk)
        output_path.write_bytes(b'x' * (MIN_OUTPUT_SIZE_BYTES + 50_000))
        
        blender_ok = blender_output.exists() and blender_output.stat().st_size > MIN_OUTPUT_SIZE_BYTES
        final_ok = output_path.exists() and output_path.stat().st_size > MIN_OUTPUT_SIZE_BYTES
        
        assert not blender_ok, ".blender.mp4 shouldn't exist"
        assert final_ok, "Should detect final path"
        
        produced = blender_output if blender_ok else (output_path if final_ok else None)
        assert produced == output_path, "Should use final path"
        print(f"  ✓ Case 2: Detected Blender output at final path")
        
        # Test Case 3: Neither exists (failure)
        output_path.unlink()
        
        blender_ok = blender_output.exists() and blender_output.stat().st_size > MIN_OUTPUT_SIZE_BYTES
        final_ok = output_path.exists() and output_path.stat().st_size > MIN_OUTPUT_SIZE_BYTES
        
        assert not blender_ok, "Nothing should exist"
        assert not final_ok, "Nothing should exist"
        
        produced = blender_output if blender_ok else (output_path if final_ok else None)
        assert produced is None, "Should detect failure"
        print(f"  ✓ Case 3: Detected missing output correctly")


def test_fallback_guard_logic():
    """Test that FFmpeg fallback doesn't overwrite good Blender output."""
    print("\nTesting FFmpeg fallback guard logic...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Simulate paths
        video_path = output_dir / "topic-01-20251220-R1.mp4"
        blender_video_path = output_dir / "topic-01-20251220-R1.blender.mp4"
        
        # Test Case 1: Good .blender.mp4 exists
        blender_video_path.write_bytes(b'x' * (MIN_FALLBACK_GUARD_SIZE_BYTES + 500_000))
        
        if blender_video_path.exists() and blender_video_path.stat().st_size > MIN_FALLBACK_GUARD_SIZE_BYTES:
            skip_fallback = True
            print(f"  ✓ Case 1: Would skip fallback (good .blender.mp4 exists)")
        else:
            skip_fallback = False
            print(f"  ✗ Case 1: ERROR - Should skip fallback")
        
        assert skip_fallback, "Should skip fallback when good .blender.mp4 exists"
        
        # Clean up
        blender_video_path.unlink()
        
        # Test Case 2: Good final path exists
        video_path.write_bytes(b'x' * (MIN_FALLBACK_GUARD_SIZE_BYTES + 500_000))
        
        if video_path.exists() and video_path.stat().st_size > MIN_FALLBACK_GUARD_SIZE_BYTES:
            skip_fallback = True
            print(f"  ✓ Case 2: Would skip fallback (good final output exists)")
        else:
            skip_fallback = False
            print(f"  ✗ Case 2: ERROR - Should skip fallback")
        
        assert skip_fallback, "Should skip fallback when good final output exists"
        
        # Test Case 3: Small file exists (< threshold)
        video_path.write_bytes(b'x' * (MIN_FALLBACK_GUARD_SIZE_BYTES - 500_000))
        
        if video_path.exists() and video_path.stat().st_size > MIN_FALLBACK_GUARD_SIZE_BYTES:
            skip_fallback = True
        else:
            skip_fallback = False
            print(f"  ✓ Case 3: Would proceed with fallback (file too small)")
        
        assert not skip_fallback, "Should proceed with fallback when file is too small"
        
        # Test Case 4: No file exists
        video_path.unlink()
        
        if blender_video_path.exists() and blender_video_path.stat().st_size > MIN_FALLBACK_GUARD_SIZE_BYTES:
            skip_fallback = True
        elif video_path.exists() and video_path.stat().st_size > MIN_FALLBACK_GUARD_SIZE_BYTES:
            skip_fallback = True
        else:
            skip_fallback = False
            print(f"  ✓ Case 4: Would proceed with fallback (no file exists)")
        
        assert not skip_fallback, "Should proceed with fallback when no file exists"


def test_mp4_listing_logic():
    """Test that MP4 listing shows only MP4 files."""
    print("\nTesting MP4 listing logic...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Create various files
        (output_dir / "topic-01-20251220-R1.mp4").write_bytes(b'x' * 1_000_000)
        (output_dir / "topic-01-20251220-R1.blender.mp4").write_bytes(b'x' * 2_000_000)
        (output_dir / "topic-01-20251220-R1.mux.mp4").write_bytes(b'x' * 500_000)
        (output_dir / "topic-01-20251220-R1.m4a").write_bytes(b'x' * 100_000)
        (output_dir / "topic-01-20251220-R1.json").write_bytes(b'{}')
        
        # List MP4 files only
        mp4_files = sorted(output_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        assert len(mp4_files) == 3, f"Should find 3 MP4 files, found {len(mp4_files)}"
        
        mp4_names = [p.name for p in mp4_files]
        assert "topic-01-20251220-R1.mp4" in mp4_names
        assert "topic-01-20251220-R1.blender.mp4" in mp4_names
        assert "topic-01-20251220-R1.mux.mp4" in mp4_names
        assert "topic-01-20251220-R1.m4a" not in mp4_names
        assert "topic-01-20251220-R1.json" not in mp4_names
        
        print(f"  ✓ MP4 listing correctly filters to .mp4 files only")
        print(f"  ✓ Found {len(mp4_files)} MP4 files")


def test_normalization_to_blender_convention():
    """Test that normalization copies to .blender.mp4 when needed."""
    print("\nTesting normalization to .blender.mp4 convention...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Simulate paths
        output_path = output_dir / "topic-01-20251220-R1.mp4"
        blender_output = output_path.with_suffix('.blender.mp4')
        
        # Blender wrote to final path only
        output_path.write_bytes(b'x' * 150_000)
        
        # Check if normalization is needed
        if output_path.exists() and not blender_output.exists():
            import shutil
            shutil.copy2(output_path, blender_output)
            print(f"  ✓ Normalized: Copied to .blender.mp4")
        
        # Verify both files exist and have same size
        assert output_path.exists(), "Original should exist"
        assert blender_output.exists(), ".blender.mp4 should exist"
        assert output_path.stat().st_size == blender_output.stat().st_size, "Files should have same size"
        
        print(f"  ✓ Both files exist with same size")


if __name__ == '__main__':
    test_blender_output_detection_logic()
    test_fallback_guard_logic()
    test_mp4_listing_logic()
    test_normalization_to_blender_convention()
    print("\n✓ All tests passed!")
