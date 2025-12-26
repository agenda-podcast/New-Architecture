#!/usr/bin/env python3
"""Test content type filtering in video rendering."""
import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from global_config import CONTENT_TYPES
from multi_format_generator import get_enabled_content_types


def extract_code_prefixes(enabled_specs):
    """
    Helper function to extract code prefixes from enabled specs.
    
    Args:
        enabled_specs: List of spec dictionaries from get_enabled_content_types()
    
    Returns:
        Set of code prefixes (e.g., {'R', 'L', 'M', 'S'})
    """
    return {spec['code'][0].upper() for spec in enabled_specs if spec.get('code') and len(spec['code']) > 0}


def test_enabled_content_types_reels_only():
    """Test get_enabled_content_types with only reels enabled."""
    print("Testing content type filtering with reels only...")
    
    config = {
        'content_types': {
            'long': False,
            'medium': False,
            'short': False,
            'reels': True
        }
    }
    
    enabled_specs = get_enabled_content_types(config)
    enabled_prefixes = extract_code_prefixes(enabled_specs)
    
    # Verify we get exactly 8 reels (R1-R8)
    assert len(enabled_specs) == 8, f"Expected 8 reels, got {len(enabled_specs)}"
    
    # Verify all have prefix 'R'
    assert enabled_prefixes == {'R'}, f"Expected only 'R' prefix, got {enabled_prefixes}"
    
    # Verify code format
    expected_codes = [f"R{i}" for i in range(1, 9)]
    actual_codes = [spec['code'] for spec in enabled_specs]
    assert actual_codes == expected_codes, f"Expected {expected_codes}, got {actual_codes}"
    
    print(f"✓ Reels-only config returns {len(enabled_specs)} specs with prefix 'R'")
    print(f"✓ Codes: {actual_codes}")


def test_fallback_to_all_content_types():
    """Test fallback behavior when no content types are enabled."""
    print("\nTesting fallback to all content types...")
    
    # Simulate the fallback logic from video_render.py
    config = {
        'content_types': {
            'long': False,
            'medium': False,
            'short': False,
            'reels': False
        }
    }
    
    enabled_specs = get_enabled_content_types(config)
    enabled_prefixes = extract_code_prefixes(enabled_specs)
    
    # When no types are enabled, enabled_prefixes should be empty
    assert len(enabled_prefixes) == 0, f"Expected empty set, got {enabled_prefixes}"
    
    # Test the fallback behavior (should use CONTENT_TYPES.values())
    fallback_prefixes = {spec.get('code_prefix', '').upper() for spec in CONTENT_TYPES.values()}
    assert fallback_prefixes == {'L', 'M', 'S', 'R'}, f"Expected all prefixes, got {fallback_prefixes}"
    
    print(f"✓ Empty config returns empty enabled_prefixes: {enabled_prefixes}")
    print(f"✓ Fallback correctly uses CONTENT_TYPES.values(): {fallback_prefixes}")


def test_multiple_content_types_enabled():
    """Test with multiple content types enabled."""
    print("\nTesting multiple content types enabled...")
    
    config = {
        'content_types': {
            'long': True,
            'medium': True,
            'short': False,
            'reels': True
        }
    }
    
    enabled_specs = get_enabled_content_types(config)
    enabled_prefixes = extract_code_prefixes(enabled_specs)
    
    # Verify we get 1 long + 2 medium + 8 reels = 11 total
    assert len(enabled_specs) == 11, f"Expected 11 specs, got {len(enabled_specs)}"
    
    # Verify we have L, M, R prefixes
    assert enabled_prefixes == {'L', 'M', 'R'}, f"Expected L, M, R prefixes, got {enabled_prefixes}"
    
    # Count by prefix
    prefix_counts = {}
    for spec in enabled_specs:
        prefix = spec['code'][0]
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    
    assert prefix_counts == {'L': 1, 'M': 2, 'R': 8}, f"Expected L:1, M:2, R:8, got {prefix_counts}"
    
    print(f"✓ Multi-type config returns {len(enabled_specs)} specs")
    print(f"✓ Prefix counts: {prefix_counts}")
    print(f"✓ Enabled prefixes: {enabled_prefixes}")


def test_content_type_check_simulation():
    """Simulate the content type check from video_render.py."""
    print("\nTesting content type check simulation...")
    
    # Simulate reels-only configuration
    config = {
        'content_types': {
            'long': False,
            'medium': False,
            'short': False,
            'reels': True
        }
    }
    
    enabled_specs = get_enabled_content_types(config)
    enabled_prefixes = extract_code_prefixes(enabled_specs)
    
    # Simulate checking audio files with different prefixes
    test_files = [
        ('topic-01-20251221-R1.m4a', 'R', True),   # Should be enabled
        ('topic-01-20251221-R5.m4a', 'R', True),   # Should be enabled
        ('topic-01-20251221-L1.m4a', 'L', False),  # Should be skipped
        ('topic-01-20251221-M1.m4a', 'M', False),  # Should be skipped
        ('topic-01-20251221-S1.m4a', 'S', False),  # Should be skipped
    ]
    
    for filename, prefix, should_be_enabled in test_files:
        is_enabled = prefix in enabled_prefixes
        assert is_enabled == should_be_enabled, \
            f"File {filename} with prefix {prefix}: expected enabled={should_be_enabled}, got {is_enabled}"
        status = "✓ enabled" if is_enabled else "✗ skipped"
        print(f"  {filename}: {status}")


def main():
    """Run all tests."""
    print("=" * 70)
    print("CONTENT TYPE FILTERING TESTS")
    print("=" * 70 + "\n")
    
    try:
        test_enabled_content_types_reels_only()
        test_fallback_to_all_content_types()
        test_multiple_content_types_enabled()
        test_content_type_check_simulation()
        
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
