#!/usr/bin/env python3
"""
Smoke test for video rendering module.

Tests basic functionality:
- Module imports without errors
- Image discovery works with supported formats
- Graceful handling of missing images
"""
import tempfile
from pathlib import Path
import subprocess

try:
    import video_render
except ImportError as e:
    print(f"Error: Failed to import video_render module: {e}")
    print("Make sure you're running this from the scripts directory")
    import sys
    sys.exit(1)


def test_module_import():
    """Test that video_render module can be imported."""
    print("Testing module import...")
    assert hasattr(video_render, 'discover_images'), "discover_images function not found"
    assert hasattr(video_render, 'render_for_topic'), "render_for_topic function not found"
    assert hasattr(video_render, 'create_video_from_images'), "create_video_from_images not found"
    print("✓ Module imported successfully with expected functions")


def test_discover_images():
    """Test image discovery with various formats."""
    print("\nTesting image discovery...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test 1: Empty directory
        images = video_render.discover_images(temp_path)
        assert images == [], f"Expected empty list, got {images}"
        print("✓ Empty directory returns empty list")
        
        # Test 2: Create test images with supported formats
        test_files = [
            'image_001.jpg',
            'image_002.jpeg',
            'image_003.png',
            'image_004.webp',
            'image_005.bmp',
            'image_006.txt',  # Unsupported format
            'readme.md',      # Unsupported format
        ]
        
        for filename in test_files:
            file_path = temp_path / filename
            file_path.touch()
        
        # Discover images
        images = video_render.discover_images(temp_path)
        
        # Should find 5 images (jpg, jpeg, png, webp, bmp), not txt or md
        assert len(images) == 5, f"Expected 5 images, found {len(images)}"
        print(f"✓ Discovered {len(images)} images (jpg, jpeg, png, webp, bmp)")
        
        # Test 3: Verify sorting order
        image_names = [img.name for img in images]
        expected_order = ['image_001.jpg', 'image_002.jpeg', 'image_003.png', 'image_004.webp', 'image_005.bmp']
        assert image_names == expected_order, f"Expected {expected_order}, got {image_names}"
        print("✓ Images sorted in lexicographic order")


def test_video_rendering_imports():
    """Test that all required constants are available."""
    print("\nTesting video rendering configuration...")
    
    # Check that VIDEO_WIDTH and VIDEO_HEIGHT are available
    from video_render import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
    assert VIDEO_WIDTH > 0, "VIDEO_WIDTH must be positive"
    assert VIDEO_HEIGHT > 0, "VIDEO_HEIGHT must be positive"
    assert VIDEO_FPS > 0, "VIDEO_FPS must be positive"
    print(f"✓ Default video configuration: {VIDEO_WIDTH}x{VIDEO_HEIGHT} @ {VIDEO_FPS}fps")
    
    # Check that allowed extensions are defined
    from global_config import ALLOWED_IMAGE_EXTENSIONS
    expected_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
    assert ALLOWED_IMAGE_EXTENSIONS == expected_extensions, \
        f"Expected {expected_extensions}, got {ALLOWED_IMAGE_EXTENSIONS}"
    print(f"✓ Allowed image formats: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")


def test_video_resolution_configuration():
    """Test video resolution configuration for different content types."""
    print("\nTesting video resolution configuration...")
    
    from global_config import (
        VIDEO_RESOLUTIONS, 
        get_video_resolution_for_code,
        get_video_resolution_for_content_type
    )
    
    # Expected resolution values (extracted for maintainability)
    EXPECTED_HORIZONTAL_WIDTH = 1920
    EXPECTED_HORIZONTAL_HEIGHT = 1080
    EXPECTED_VERTICAL_WIDTH = 1080
    EXPECTED_VERTICAL_HEIGHT = 1920
    
    # Test resolution configurations exist
    assert 'horizontal' in VIDEO_RESOLUTIONS, "Horizontal resolution not defined"
    assert 'vertical' in VIDEO_RESOLUTIONS, "Vertical resolution not defined"
    
    horizontal = VIDEO_RESOLUTIONS['horizontal']
    vertical = VIDEO_RESOLUTIONS['vertical']
    
    assert horizontal['width'] == EXPECTED_HORIZONTAL_WIDTH, \
        f"Expected horizontal width {EXPECTED_HORIZONTAL_WIDTH}, got {horizontal['width']}"
    assert horizontal['height'] == EXPECTED_HORIZONTAL_HEIGHT, \
        f"Expected horizontal height {EXPECTED_HORIZONTAL_HEIGHT}, got {horizontal['height']}"
    assert vertical['width'] == EXPECTED_VERTICAL_WIDTH, \
        f"Expected vertical width {EXPECTED_VERTICAL_WIDTH}, got {vertical['width']}"
    assert vertical['height'] == EXPECTED_VERTICAL_HEIGHT, \
        f"Expected vertical height {EXPECTED_VERTICAL_HEIGHT}, got {vertical['height']}"
    
    print(f"✓ Horizontal resolution: {horizontal['width']}x{horizontal['height']}")
    print(f"✓ Vertical resolution: {vertical['width']}x{vertical['height']}")
    
    # Test content type to resolution mapping
    # Long and Medium should use horizontal
    width, height = get_video_resolution_for_content_type('long')
    assert (width, height) == (EXPECTED_HORIZONTAL_WIDTH, EXPECTED_HORIZONTAL_HEIGHT), \
        f"Long format should be horizontal {EXPECTED_HORIZONTAL_WIDTH}x{EXPECTED_HORIZONTAL_HEIGHT}, got {width}x{height}"
    
    width, height = get_video_resolution_for_content_type('medium')
    assert (width, height) == (EXPECTED_HORIZONTAL_WIDTH, EXPECTED_HORIZONTAL_HEIGHT), \
        f"Medium format should be horizontal {EXPECTED_HORIZONTAL_WIDTH}x{EXPECTED_HORIZONTAL_HEIGHT}, got {width}x{height}"
    
    # Short and Reels should use vertical
    width, height = get_video_resolution_for_content_type('short')
    assert (width, height) == (EXPECTED_VERTICAL_WIDTH, EXPECTED_VERTICAL_HEIGHT), \
        f"Short format should be vertical {EXPECTED_VERTICAL_WIDTH}x{EXPECTED_VERTICAL_HEIGHT}, got {width}x{height}"
    
    width, height = get_video_resolution_for_content_type('reels')
    assert (width, height) == (EXPECTED_VERTICAL_WIDTH, EXPECTED_VERTICAL_HEIGHT), \
        f"Reels format should be vertical {EXPECTED_VERTICAL_WIDTH}x{EXPECTED_VERTICAL_HEIGHT}, got {width}x{height}"
    
    print("✓ Content type mappings:")
    print(f"  - Long (L) → horizontal {EXPECTED_HORIZONTAL_WIDTH}x{EXPECTED_HORIZONTAL_HEIGHT}")
    print(f"  - Medium (M) → horizontal {EXPECTED_HORIZONTAL_WIDTH}x{EXPECTED_HORIZONTAL_HEIGHT}")
    print(f"  - Short (S) → vertical {EXPECTED_VERTICAL_WIDTH}x{EXPECTED_VERTICAL_HEIGHT}")
    print(f"  - Reels (R) → vertical {EXPECTED_VERTICAL_WIDTH}x{EXPECTED_VERTICAL_HEIGHT}")
    
    # Test code-based resolution lookup
    assert get_video_resolution_for_code('L1') == (EXPECTED_HORIZONTAL_WIDTH, EXPECTED_HORIZONTAL_HEIGHT), \
        "L1 should be horizontal"
    assert get_video_resolution_for_code('M2') == (EXPECTED_HORIZONTAL_WIDTH, EXPECTED_HORIZONTAL_HEIGHT), \
        "M2 should be horizontal"
    assert get_video_resolution_for_code('S3') == (EXPECTED_VERTICAL_WIDTH, EXPECTED_VERTICAL_HEIGHT), \
        "S3 should be vertical"
    assert get_video_resolution_for_code('R4') == (EXPECTED_VERTICAL_WIDTH, EXPECTED_VERTICAL_HEIGHT), \
        "R4 should be vertical"
    
    print("✓ Code-based resolution lookup working correctly")


def test_ffmpeg_uses_even_scaled_dimensions(monkeypatch, tmp_path):
    """Ensure FFmpeg command scales and pads to even target dimensions."""
    commands = []

    def fake_run(cmd, check=False, capture_output=False, text=False, timeout=None):
        commands.append(cmd)
        if cmd[0] == 'ffprobe':
            # First ffprobe returns duration, second returns duration and size
            if 'format=duration' in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="4.0\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="4.0\n1000\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(video_render.subprocess, "run", fake_run)
    images = []
    for idx in range(2):
        img_path = tmp_path / f"img_{idx}.jpg"
        img_path.write_bytes(b"data")
        images.append(img_path)

    audio_path = tmp_path / "audio.m4a"
    audio_path.write_bytes(b"audio")
    output_path = tmp_path / "output.mp4"

    config = {
        "video_width": 595,   # odd to trigger even rounding
        "video_height": 856,  # already even
        "video_fps": 24,
    }

    assert video_render.create_video_from_images(
        images, audio_path, output_path, config, chapters=[], content_code="R1"
    )

    ffmpeg_cmd = next(cmd for cmd in commands if cmd and cmd[0] == 'ffmpeg')
    vf_index = ffmpeg_cmd.index('-vf')
    filter_str = ffmpeg_cmd[vf_index + 1]
    expected_filter = (
        "scale=596:856:force_original_aspect_ratio=decrease,"
        "pad=596:856:(ow-iw)/2:(oh-ih)/2"
    )
    assert filter_str == expected_filter


def test_ffmpeg_available():
    """Test that ffmpeg is available for video rendering."""
    print("\nTesting ffmpeg availability...")
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, check=True)
        version_line = result.stdout.split('\n')[0]
        print(f"✓ FFmpeg available: {version_line}")
    except FileNotFoundError:
        print("⚠ Warning: ffmpeg not found - video rendering will fail")
        print("  Install ffmpeg to enable video rendering")
    except Exception as e:
        print(f"⚠ Warning: Error checking ffmpeg: {e}")


def main():
    """Run all tests."""
    print("="*60)
    print("Video Render Module Smoke Tests")
    print("="*60)
    
    try:
        test_module_import()
        test_discover_images()
        test_video_rendering_imports()
        test_video_resolution_configuration()
        test_ffmpeg_available()
        
        print("\n" + "="*60)
        print("✓ All tests passed!")
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
    import sys
    sys.exit(main())
