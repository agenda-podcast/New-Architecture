#!/usr/bin/env python3
"""
Test for get_blender_output_path helper function.
"""
from pathlib import Path
import sys

# Add the scripts directory to the path so we can import video_render
sys.path.insert(0, str(Path(__file__).parent))

from video_render import get_blender_output_path


def test_get_blender_output_path():
    """Test the get_blender_output_path helper function."""
    print("Testing get_blender_output_path helper function...")
    
    # Test 1: Plain .mp4 path
    path1 = Path("/outputs/topic-01/topic-01-20251220-R1.mp4")
    result1 = get_blender_output_path(path1)
    expected1 = Path("/outputs/topic-01/topic-01-20251220-R1.blender.mp4")
    assert result1 == expected1, f"Expected {expected1}, got {result1}"
    print(f"  ✓ Test 1: {path1.name} -> {result1.name}")
    
    # Test 2: Already has .blender.mp4 (idempotent)
    path2 = Path("/outputs/topic-01/topic-01-20251220-R1.blender.mp4")
    result2 = get_blender_output_path(path2)
    expected2 = Path("/outputs/topic-01/topic-01-20251220-R1.blender.mp4")
    assert result2 == expected2, f"Expected {expected2}, got {result2}"
    print(f"  ✓ Test 2: {path2.name} -> {result2.name} (idempotent)")
    
    # Test 3: Different directory
    path3 = Path("/tmp/test/video.mp4")
    result3 = get_blender_output_path(path3)
    expected3 = Path("/tmp/test/video.blender.mp4")
    assert result3 == expected3, f"Expected {expected3}, got {result3}"
    print(f"  ✓ Test 3: {path3.name} -> {result3.name}")
    
    # Test 4: Complex filename
    path4 = Path("/outputs/topic-99/topic-99-20251231-M5.mp4")
    result4 = get_blender_output_path(path4)
    expected4 = Path("/outputs/topic-99/topic-99-20251231-M5.blender.mp4")
    assert result4 == expected4, f"Expected {expected4}, got {result4}"
    print(f"  ✓ Test 4: {path4.name} -> {result4.name}")
    
    # Test 5: Multiple calls (ensure truly idempotent)
    path5 = Path("/outputs/topic-01/video.mp4")
    result5a = get_blender_output_path(path5)
    result5b = get_blender_output_path(result5a)
    assert result5a == result5b, f"Function not idempotent: {result5a} != {result5b}"
    print(f"  ✓ Test 5: Multiple calls are idempotent")


if __name__ == '__main__':
    test_get_blender_output_path()
    print("\n✓ All tests passed!")
