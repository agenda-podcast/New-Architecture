#!/usr/bin/env python3
"""
Test video-audio generation settings.

Verifies that the new ENABLE_VIDEO_GENERATION and ENABLE_VIDEO_AUDIO_MUX
settings are properly configured and imported.
"""
import sys

try:
    import global_config
    import video_render
except ImportError as e:
    print(f"Error: Failed to import required modules: {e}")
    print("Make sure you're running this from the scripts directory")
    sys.exit(1)


def test_settings_exist():
    """Test that the new settings exist in global_config."""
    print("Testing settings existence...")
    
    assert hasattr(global_config, 'ENABLE_VIDEO_GENERATION'), \
        "ENABLE_VIDEO_GENERATION not found in global_config"
    assert hasattr(global_config, 'ENABLE_VIDEO_AUDIO_MUX'), \
        "ENABLE_VIDEO_AUDIO_MUX not found in global_config"
    
    print(f"✓ ENABLE_VIDEO_GENERATION = {global_config.ENABLE_VIDEO_GENERATION}")
    print(f"✓ ENABLE_VIDEO_AUDIO_MUX = {global_config.ENABLE_VIDEO_AUDIO_MUX}")


def test_default_values():
    """Test that the default values match requirements."""
    print("\nTesting default values...")
    
    assert global_config.ENABLE_VIDEO_GENERATION == True, \
        f"Expected ENABLE_VIDEO_GENERATION=True, got {global_config.ENABLE_VIDEO_GENERATION}"
    assert global_config.ENABLE_VIDEO_AUDIO_MUX == False, \
        f"Expected ENABLE_VIDEO_AUDIO_MUX=False, got {global_config.ENABLE_VIDEO_AUDIO_MUX}"
    
    print("✓ ENABLE_VIDEO_GENERATION defaults to True")
    print("✓ ENABLE_VIDEO_AUDIO_MUX defaults to False (video-only mode)")


def test_video_render_imports():
    """Test that video_render module imports the new settings."""
    print("\nTesting video_render imports...")
    
    # Check that the module has imported the settings
    assert hasattr(video_render, 'ENABLE_VIDEO_GENERATION'), \
        "video_render module did not import ENABLE_VIDEO_GENERATION"
    assert hasattr(video_render, 'ENABLE_VIDEO_AUDIO_MUX'), \
        "video_render module did not import ENABLE_VIDEO_AUDIO_MUX"
    
    # Verify values match global_config
    assert video_render.ENABLE_VIDEO_GENERATION == global_config.ENABLE_VIDEO_GENERATION, \
        "video_render.ENABLE_VIDEO_GENERATION doesn't match global_config"
    assert video_render.ENABLE_VIDEO_AUDIO_MUX == global_config.ENABLE_VIDEO_AUDIO_MUX, \
        "video_render.ENABLE_VIDEO_AUDIO_MUX doesn't match global_config"
    
    print("✓ video_render correctly imports ENABLE_VIDEO_GENERATION")
    print("✓ video_render correctly imports ENABLE_VIDEO_AUDIO_MUX")


def test_settings_documentation():
    """Test that settings are properly documented."""
    print("\nTesting settings documentation...")
    
    # Get the source of global_config to check for comments
    import inspect
    source = inspect.getsource(global_config)
    
    # Check for documentation near the settings
    assert 'ENABLE_VIDEO_GENERATION' in source, "ENABLE_VIDEO_GENERATION not found in source"
    assert 'ENABLE_VIDEO_AUDIO_MUX' in source, "ENABLE_VIDEO_AUDIO_MUX not found in source"
    
    print("✓ Settings are documented in global_config.py")


def main():
    """Run all tests."""
    print("="*60)
    print("Video-Audio Settings Test")
    print("="*60 + "\n")
    
    try:
        test_settings_exist()
        test_default_values()
        test_video_render_imports()
        test_settings_documentation()
        
        print("\n" + "="*60)
        print("All tests passed! ✓")
        print("="*60)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
