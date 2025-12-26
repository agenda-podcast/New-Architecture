#!/usr/bin/env python3
"""
Test for caption burn-in fix.

This test verifies that the _build_drawtext_vf function generates
correct FFmpeg filter strings for caption overlays, specifically
ensuring that the 'enable' parameter is properly formatted.

Note: This test imports a private function (_build_drawtext_vf) for
targeted unit testing of a specific bug fix. This is acceptable practice
for regression testing of internal implementation details.
"""
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from video_render import _build_drawtext_vf


def test_enable_parameter_format():
    """Test that enable parameter is correctly formatted without outer quotes."""
    print("Testing enable parameter format in drawtext filter...")
    
    # Sample captions with timing
    captions = [
        (0.0, 2.5, "Hello world"),
        (3.0, 5.0, "This is a test"),
    ]
    
    # Generate filter string for TikTok style
    vf = _build_drawtext_vf(
        captions,
        font_size=63,
        margin_v=384,
        margin_lr=50,
        style="tiktok"
    )
    
    print(f"\nGenerated filter string (first 500 chars):")
    print(f"{vf[:500]}...\n")
    
    # Verify that enable parameter does NOT have outer quotes
    # Should be: enable=between(t\,0.000\,2.500)
    # NOT: enable='between(t\,0.000\,2.500)'
    
    # Check for incorrect pattern (with quotes)
    if "enable='between" in vf:
        print("✗ FAIL: enable parameter has incorrect outer quotes")
        print(f"   Found: enable='between...")
        print(f"   Expected: enable=between...")
        return False
    
    # Check for correct pattern (without quotes around between)
    if "enable=between(t\\," not in vf:
        print("✗ FAIL: enable parameter not found in expected format")
        print(f"   Expected pattern: enable=between(t\\,...")
        return False
    
    # Verify commas are escaped inside between()
    if "between(t," in vf:  # Unescaped comma (wrong)
        print("✗ FAIL: Commas in between() are not escaped")
        print(f"   Found: between(t,...")
        print(f"   Expected: between(t\\,...")
        return False
    
    print("✓ PASS: enable parameter is correctly formatted")
    print(f"   Pattern: enable=between(t\\,START\\,END)")
    return True


def test_boxed_style():
    """Test that boxed style also has correct enable format."""
    print("\nTesting boxed style enable parameter format...")
    
    captions = [(1.0, 3.0, "Boxed caption")]
    
    vf = _build_drawtext_vf(
        captions,
        font_size=48,
        margin_v=100,
        margin_lr=40,
        style="boxed"
    )
    
    # Same checks as TikTok style
    if "enable='between" in vf:
        print("✗ FAIL: enable parameter has incorrect outer quotes")
        return False
    
    if "enable=between(t\\," not in vf:
        print("✗ FAIL: enable parameter not found in expected format")
        return False
    
    print("✓ PASS: boxed style enable parameter is correctly formatted")
    return True


def test_multiple_captions():
    """Test that multiple captions are all correctly formatted."""
    print("\nTesting multiple captions...")
    
    captions = [
        (0.0, 2.5, "Caption one"),
        (3.0, 5.5, "Caption two"),
        (6.0, 8.0, "Caption three"),
    ]
    
    vf = _build_drawtext_vf(
        captions,
        font_size=63,
        margin_v=384,
        margin_lr=50,
        style="tiktok"
    )
    
    # Count enable parameters
    enable_count = vf.count("enable=between")
    expected_count = len(captions) * 2  # TikTok style has 2 drawtext per caption (glow + main)
    
    if enable_count != expected_count:
        print(f"✗ FAIL: Expected {expected_count} enable parameters, found {enable_count}")
        return False
    
    # Verify no quoted enables
    if "enable='" in vf:
        print("✗ FAIL: Found enable parameter with incorrect quotes")
        return False
    
    print(f"✓ PASS: All {enable_count} enable parameters are correctly formatted")
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("Caption Burn-in Fix Validation Tests")
    print("="*60)
    
    tests = [
        test_enable_parameter_format,
        test_boxed_style,
        test_multiple_captions,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ EXCEPTION in {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
