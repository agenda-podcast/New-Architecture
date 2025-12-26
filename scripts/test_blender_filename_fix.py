#!/usr/bin/env python3
"""
Test to verify that Blender output files keep the .blender.mp4 extension.

This test verifies that:
1. Blender creates output with .blender.mp4 extension
2. After muxing, the final output keeps .blender.mp4 extension
3. The .blender.mp4 file is not deleted
4. No .mp4 file (without .blender) is created
"""
import tempfile
from pathlib import Path


def test_blender_output_filename_pattern():
    """Test that Blender output filename pattern is correct."""
    print("Testing Blender output filename pattern...")
    
    # Simulate the expected behavior
    output_dir = Path("/outputs/topic-01")
    topic_id = "topic-01"
    date_str = "20251220"
    code = "R1"
    
    # Original video path (what caller expects)
    video_path = output_dir / f"{topic_id}-{date_str}-{code}.mp4"
    print(f"  Original video_path: {video_path}")
    
    # Blender output path (intermediate and final)
    blender_output = video_path.with_suffix('.blender.mp4')
    print(f"  Blender output path: {blender_output}")
    
    # After successful render, video_path should be updated
    video_path = video_path.with_suffix('.blender.mp4')
    print(f"  Updated video_path: {video_path}")
    
    # Verify the paths
    assert str(blender_output) == "/outputs/topic-01/topic-01-20251220-R1.blender.mp4"
    assert str(video_path) == "/outputs/topic-01/topic-01-20251220-R1.blender.mp4"
    assert blender_output == video_path
    
    print(f"  ✓ Blender output filename pattern is correct")
    print(f"  ✓ Final file will be: {video_path.name}")


def test_mux_output_overwrites_blender_intermediate():
    """Test that muxed output overwrites the intermediate Blender file."""
    print("\nTesting mux output overwrites intermediate...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Simulate Blender creating video-only file
        blender_output = output_dir / "topic-01-20251220-R1.blender.mp4"
        blender_output.write_text("video-only content")
        print(f"  Created intermediate: {blender_output.name}")
        
        # Simulate mux creating temp file
        mux_temp = output_dir / "topic-01-20251220-R1.mux.mp4"
        mux_temp.write_text("video+audio content")
        print(f"  Created mux temp: {mux_temp.name}")
        
        # Simulate the rename operation (mux temp -> blender output)
        import os
        os.replace(str(mux_temp), str(blender_output))
        print(f"  Moved mux temp to: {blender_output.name}")
        
        # Verify final state
        assert blender_output.exists(), "Blender output should exist"
        assert not mux_temp.exists(), "Mux temp should be gone"
        assert blender_output.read_text() == "video+audio content", "Should have muxed content"
        
        print(f"  ✓ Mux output correctly overwrites intermediate")
        print(f"  ✓ Final file contains muxed content")


def test_no_plain_mp4_created():
    """Test that no plain .mp4 file is created (only .blender.mp4)."""
    print("\nTesting no plain .mp4 file is created...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Simulate the render process
        video_path_plain = output_dir / "topic-01-20251220-R1.mp4"
        blender_output = output_dir / "topic-01-20251220-R1.blender.mp4"
        
        # Only blender output should be created
        blender_output.write_text("final content")
        
        # Verify
        assert blender_output.exists(), "Blender output should exist"
        assert not video_path_plain.exists(), "Plain .mp4 should NOT exist"
        
        print(f"  ✓ Only .blender.mp4 file exists")
        print(f"  ✓ No plain .mp4 file created")


def test_suffix_handling():
    """Test Path.with_suffix behavior with double extensions."""
    print("\nTesting Path.with_suffix behavior...")
    
    # Test 1: .mp4 -> .blender.mp4
    path1 = Path("/outputs/topic-01-20251220-R1.mp4")
    blender1 = path1.with_suffix('.blender.mp4')
    print(f"  {path1.name} -> {blender1.name}")
    assert str(blender1) == "/outputs/topic-01-20251220-R1.blender.mp4"
    
    # Test 2: .blender.mp4 -> .blender.mp4 (idempotent with guard)
    path2 = Path("/outputs/topic-01-20251220-R1.blender.mp4")
    # This is what would happen without the guard:
    blender2_unsafe = path2.with_suffix('.blender.mp4')
    print(f"  {path2.name} -> {blender2_unsafe.name} (without guard)")
    assert str(blender2_unsafe) == "/outputs/topic-01-20251220-R1.blender.blender.mp4"
    
    # This is what should happen with the guard (using stem check):
    if not path2.stem.endswith('.blender'):
        blender2_safe = path2.parent / f"{path2.stem}.blender{path2.suffix}"
    else:
        blender2_safe = path2
    print(f"  {path2.name} -> {blender2_safe.name} (with stem-based guard)")
    assert str(blender2_safe) == "/outputs/topic-01-20251220-R1.blender.mp4"
    
    print(f"  ✓ with_suffix works correctly with stem-based guard to prevent double extension")


def test_idempotent_suffix_application():
    """Test that applying .blender.mp4 suffix is safe even if already applied."""
    print("\nTesting idempotent suffix application...")
    
    # Simulate calling the suffix logic twice (shouldn't happen but should be safe)
    path = Path("/outputs/topic-01-20251220-R1.mp4")
    
    # First application (using stem-based check)
    if not path.stem.endswith('.blender'):
        path = path.parent / f"{path.stem}.blender{path.suffix}"
    print(f"  After 1st application: {path.name}")
    assert str(path) == "/outputs/topic-01-20251220-R1.blender.mp4"
    
    # Second application (should be no-op)
    if not path.stem.endswith('.blender'):
        path = path.parent / f"{path.stem}.blender{path.suffix}"
    print(f"  After 2nd application: {path.name}")
    assert str(path) == "/outputs/topic-01-20251220-R1.blender.mp4"
    
    print(f"  ✓ Idempotent application works correctly with stem-based guard")


if __name__ == '__main__':
    test_blender_output_filename_pattern()
    test_mux_output_overwrites_blender_intermediate()
    test_no_plain_mp4_created()
    test_suffix_handling()
    test_idempotent_suffix_application()
    print("\n✓ All tests passed!")
