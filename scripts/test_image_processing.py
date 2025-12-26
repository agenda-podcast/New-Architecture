#!/usr/bin/env python3
"""
Test image processing functionality for social video effects.

Tests:
1. Image dimension detection
2. Blurred background composite creation
3. Image processing pipeline
"""
import sys
import tempfile
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from video_render import (
    get_image_dimensions,
    create_blurred_background_composite,
    process_images_for_video
)

# Test configuration
MIN_COMPOSITE_FILE_SIZE_BYTES = 10_000  # Minimum expected file size for composites (10KB)

def create_test_image(width: int, height: int, output_path: Path) -> bool:
    """Create a test image with specific dimensions using FFmpeg."""
    try:
        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=blue:s={width}x{height}:d=1',
            '-frames:v', '1',
            str(output_path)
        ], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to create test image: {e}")
        return False


def test_image_dimension_detection():
    """Test get_image_dimensions function."""
    print("\n" + "="*60)
    print("TEST: Image Dimension Detection")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create test images with known dimensions
        test_cases = [
            (640, 480, "small_image.jpg"),
            (1920, 1080, "full_hd_image.jpg"),
            (1080, 1920, "vertical_image.jpg"),
        ]
        
        for width, height, filename in test_cases:
            img_path = tmpdir_path / filename
            if create_test_image(width, height, img_path):
                detected_width, detected_height = get_image_dimensions(img_path)
                
                if detected_width == width and detected_height == height:
                    print(f"✓ {filename}: {detected_width}x{detected_height} (expected: {width}x{height})")
                else:
                    print(f"✗ {filename}: {detected_width}x{detected_height} (expected: {width}x{height})")
                    return False
            else:
                print(f"✗ Failed to create test image: {filename}")
                return False
    
    print("✓ All dimension detection tests passed")
    return True


def test_blurred_background_composite():
    """Test create_blurred_background_composite function."""
    print("\n" + "="*60)
    print("TEST: Blurred Background Composite Creation")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create a small test image (640x480)
        input_img = tmpdir_path / "input.jpg"
        if not create_test_image(640, 480, input_img):
            print("✗ Failed to create input image")
            return False
        
        # Create composite for 1920x1080 target
        output_img = tmpdir_path / "composite.jpg"
        target_width, target_height = 1920, 1080
        
        print(f"Creating composite from {input_img.name} (640x480) to {target_width}x{target_height}...")
        
        if create_blurred_background_composite(input_img, output_img, target_width, target_height):
            # Verify output exists and has correct dimensions
            if output_img.exists():
                out_width, out_height = get_image_dimensions(output_img)
                
                if out_width == target_width and out_height == target_height:
                    print(f"✓ Composite created successfully: {out_width}x{out_height}")
                    
                    # Check file size (should be reasonable)
                    file_size = output_img.stat().st_size
                    if file_size > MIN_COMPOSITE_FILE_SIZE_BYTES:
                        print(f"✓ Composite has reasonable file size: {file_size / 1024:.1f} KB")
                    else:
                        print(f"✗ Composite file is too small: {file_size} bytes")
                        return False
                else:
                    print(f"✗ Composite has wrong dimensions: {out_width}x{out_height}")
                    return False
            else:
                print(f"✗ Composite file not created")
                return False
        else:
            print(f"✗ create_blurred_background_composite failed")
            return False
    
    print("✓ Blurred background composite test passed")
    return True


def test_image_processing_pipeline():
    """Test process_images_for_video function."""
    print("\n" + "="*60)
    print("TEST: Image Processing Pipeline")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create test images of various sizes
        test_images = [
            (1920, 1080, "full_size.jpg"),     # Adequate size
            (640, 480, "undersized.jpg"),       # Needs composite
            (1080, 1920, "vertical.jpg"),       # Adequate for vertical
            (800, 600, "small.jpg"),            # Needs composite
        ]
        
        input_images = []
        for width, height, filename in test_images:
            img_path = tmpdir_path / filename
            if create_test_image(width, height, img_path):
                input_images.append(img_path)
            else:
                print(f"✗ Failed to create test image: {filename}")
                return False
        
        # Process images for 1920x1080 video
        target_width, target_height = 1920, 1080
        output_dir = tmpdir_path / "output"
        output_dir.mkdir(exist_ok=True)
        
        print(f"\nProcessing {len(input_images)} images for {target_width}x{target_height} video...")
        
        processed_images = process_images_for_video(
            input_images,
            target_width,
            target_height,
            output_dir
        )
        
        # Verify results
        if len(processed_images) != len(input_images):
            print(f"✗ Expected {len(input_images)} processed images, got {len(processed_images)}")
            return False
        
        print(f"✓ Processed {len(processed_images)} images")
        
        # Check that all processed images exist
        for img in processed_images:
            if not img.exists():
                print(f"✗ Processed image does not exist: {img}")
                return False
        
        print(f"✓ All processed images exist")
        
        # Count composites created
        processed_dir = output_dir / 'processed'
        if processed_dir.exists():
            composites = list(processed_dir.glob('composite_*.jpg'))
            print(f"✓ Created {len(composites)} blurred background composites")
        
    print("✓ Image processing pipeline test passed")
    return True


def main():
    """Run all tests."""
    print("Testing Image Processing for Social Video Effects")
    print("="*60)
    
    # Check if FFmpeg/ffprobe are available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("✗ FFmpeg and ffprobe are required for these tests")
        print("  Install with: sudo apt-get install ffmpeg")
        return 1
    
    tests = [
        ("Dimension Detection", test_image_dimension_detection),
        ("Blurred Background Composite", test_blurred_background_composite),
        ("Image Processing Pipeline", test_image_processing_pipeline),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\n✗ {test_name} failed")
        except Exception as e:
            failed += 1
            print(f"\n✗ {test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
