#!/usr/bin/env python3
"""
Test FFmpeg effects configuration and helper functions.

Tests:
- Config file loading
- Transition detection
- Content type inference
- Effects configuration structure
"""
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import video_render
    from global_config import ENABLE_FFMPEG_EFFECTS, FFMPEG_EFFECTS_CONFIG
except ImportError as e:
    print(f"Error: Failed to import required modules: {e}")
    sys.exit(1)


def test_config_flags():
    """Test that config flags are defined."""
    print("Testing config flags...")
    assert isinstance(ENABLE_FFMPEG_EFFECTS, bool), "ENABLE_FFMPEG_EFFECTS should be boolean"
    assert isinstance(FFMPEG_EFFECTS_CONFIG, str), "FFMPEG_EFFECTS_CONFIG should be string"
    print(f"  ENABLE_FFMPEG_EFFECTS: {ENABLE_FFMPEG_EFFECTS}")
    print(f"  FFMPEG_EFFECTS_CONFIG: {FFMPEG_EFFECTS_CONFIG}")
    print("✓ Config flags defined correctly")


def test_load_ffmpeg_effects_config():
    """Test loading FFmpeg effects configuration."""
    print("\nTesting FFmpeg effects config loading...")
    config = video_render.load_ffmpeg_effects_config()
    
    if not config:
        print("  ⚠ Warning: Config file not found or empty (expected in fresh setup)")
        return
    
    # Verify structure
    assert 'transitions' in config, "Config should have 'transitions' section"
    assert 'kenburns' in config, "Config should have 'kenburns' section"
    assert 'still_duration' in config, "Config should have 'still_duration' section"
    assert 'finishing' in config, "Config should have 'finishing' section"
    
    # Check transitions for each content type
    transitions = config['transitions']
    for content_type in ['long', 'medium', 'short', 'reels']:
        assert content_type in transitions, f"Transitions should have '{content_type}' config"
        type_config = transitions[content_type]
        assert 'transitions' in type_config, f"{content_type} should have transitions list"
        assert 'duration' in type_config, f"{content_type} should have duration"
        assert isinstance(type_config['transitions'], list), f"{content_type} transitions should be list"
        assert isinstance(type_config['duration'], (int, float)), f"{content_type} duration should be numeric"
    
    print("✓ Config structure valid")
    print(f"  Content types configured: {', '.join(transitions.keys())}")
    print(f"  Ken Burns enabled: {config['kenburns'].get('enabled', False)}")


def test_get_available_xfade_transitions():
    """Test xfade transition detection."""
    print("\nTesting xfade transition detection...")
    transitions = video_render.get_available_xfade_transitions()
    
    assert isinstance(transitions, list), "Should return list"
    
    if not transitions:
        print("  ⚠ No xfade transitions available (FFmpeg may not have xfade filter)")
    else:
        print(f"✓ Found {len(transitions)} transitions")
        print(f"  Sample transitions: {', '.join(transitions[:5])}")


def test_infer_content_type_from_code():
    """Test content type inference from code."""
    print("\nTesting content type inference...")
    
    test_cases = [
        ('L1', 'long'),
        ('L10', 'long'),
        ('M1', 'medium'),
        ('M2', 'medium'),
        ('S1', 'short'),
        ('S4', 'short'),
        ('R1', 'reels'),
        ('R8', 'reels'),
        ('', 'long'),  # Default
        ('X1', 'long'),  # Unknown -> default
    ]
    
    for code, expected in test_cases:
        result = video_render.infer_content_type_from_code(code)
        assert result == expected, f"Code '{code}' should map to '{expected}', got '{result}'"
        print(f"  {code or '(empty)':8} → {result}")
    
    print("✓ Content type inference working correctly")


def test_render_slideshow_ffmpeg_effects():
    """Test FFmpeg effects rendering function (basic validation)."""
    print("\nTesting FFmpeg effects rendering function...")
    
    # Verify function exists and has correct signature
    assert hasattr(video_render, 'render_slideshow_ffmpeg_effects'), "Function should exist"
    
    import inspect
    sig = inspect.signature(video_render.render_slideshow_ffmpeg_effects)
    params = list(sig.parameters.keys())
    
    expected_params = ['images', 'output_path', 'duration', 'width', 'height', 'fps', 'content_type', 'seed']
    for param in expected_params:
        assert param in params, f"Function should have '{param}' parameter"
    
    print("✓ Function signature correct")
    print(f"  Parameters: {', '.join(params)}")


def main():
    """Run all tests."""
    print("="*60)
    print("FFmpeg Effects Configuration Tests")
    print("="*60)
    
    try:
        test_config_flags()
        test_load_ffmpeg_effects_config()
        test_get_available_xfade_transitions()
        test_infer_content_type_from_code()
        test_render_slideshow_ffmpeg_effects()
        
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
    sys.exit(main())
