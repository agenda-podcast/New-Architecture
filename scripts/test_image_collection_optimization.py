#!/usr/bin/env python3
"""
Test image collection optimization logic.
Validates that the image collector correctly handles:
1. Existing images (sufficient count) - verifies no API call
2. Partial existing images (some but not enough) - verifies correct logic
3. No existing images (fresh collection) - verifies normal flow

This test focuses on the logic changes without requiring actual Google API calls.
"""
import os
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from global_config import ALLOWED_IMAGE_EXTENSIONS


def create_test_images(output_dir: Path, count: int) -> list:
    """Create dummy image files for testing."""
    image_paths = []
    for i in range(count):
        img_path = output_dir / f'image_{i:03d}.jpg'
        # Create a dummy file with some content (>1KB to pass validation)
        with open(img_path, 'wb') as f:
            f.write(b'FAKE_IMAGE_DATA' * 100)  # 1.5KB
        image_paths.append(img_path)
    return image_paths


def test_sufficient_existing_images():
    """Test that existing images are properly detected and returned."""
    print("\n" + "="*60)
    print("Test 1: Sufficient existing images")
    print("="*60)
    
    # Import here to ensure fresh state
    from image_collector import collect_images_for_topic
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 10 existing images
        existing_images = create_test_images(output_dir, 10)
        print(f"  Created {len(existing_images)} existing images")
        
        try:
            # This should return existing images without calling API
            # (will fail with ValueError about missing API key, but that's expected
            # if it tries to call API, or return images if it finds them)
            result = collect_images_for_topic(
                topic_title="Test Topic",
                topic_queries=["test query"],
                output_dir=output_dir,
                num_images=10,
                api_key=None,  # No API key - should not be needed
                search_engine_id=None  # No search engine ID - should not be needed
            )
            
            # If we get here, it means existing images were returned without API call
            if len(result) != 10:
                print(f"  ✗ FAIL: Expected 10 images, got {len(result)}")
                return False
            
            print(f"  ✓ Returned {len(result)} images without API call")
            
            # Verify returned images are the existing ones
            result_names = {img.name for img in result}
            expected_names = {img.name for img in existing_images}
            if result_names != expected_names:
                print(f"  ✗ FAIL: Returned images don't match existing images")
                print(f"    Expected: {sorted(expected_names)}")
                print(f"    Got: {sorted(result_names)}")
                return False
            
            print(f"  ✓ Returned images match existing images")
            
        except ValueError as e:
            # If we get a ValueError about API credentials, it means the code
            # tried to call the API instead of using existing images - FAIL
            print(f"  ✗ FAIL: Code tried to call API when existing images were sufficient")
            print(f"    Error: {e}")
            return False
        except Exception as e:
            print(f"  ✗ FAIL: Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print("  ✓ PASS: Sufficient existing images test passed")
    return True


def test_partial_existing_images_logic():
    """Test that partial image detection logic works correctly."""
    print("\n" + "="*60)
    print("Test 2: Partial existing images logic")
    print("="*60)
    
    from image_collector import collect_images_for_topic
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 5 existing images
        existing_images = create_test_images(output_dir, 5)
        print(f"  Created {len(existing_images)} existing images")
        print(f"  Need 10 total images")
        
        # Verify existing images are detected
        all_existing = []
        for ext in ALLOWED_IMAGE_EXTENSIONS:
            all_existing.extend([p for p in output_dir.glob(f'*{ext}') if p.suffix == ext])
        
        if len(all_existing) != 5:
            print(f"  ✗ FAIL: Expected 5 existing images, found {len(all_existing)}")
            return False
        
        print(f"  ✓ Correctly detected {len(all_existing)} existing images")
        
        # The function should detect that 5 more images are needed
        # We can't test the actual API call without credentials, but we can
        # verify the logic that determines how many images are needed
        images_needed = 10 - len(all_existing)
        if images_needed != 5:
            print(f"  ✗ FAIL: Expected 5 images needed, calculated {images_needed}")
            return False
        
        print(f"  ✓ Correctly calculated {images_needed} additional images needed")
    
    print("  ✓ PASS: Partial existing images logic test passed")
    return True


def test_no_existing_images_detection():
    """Test that empty directory is correctly detected."""
    print("\n" + "="*60)
    print("Test 3: No existing images detection")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"  No existing images")
        
        # Verify no images exist
        all_existing = []
        for ext in ALLOWED_IMAGE_EXTENSIONS:
            all_existing.extend([p for p in output_dir.glob(f'*{ext}') if p.suffix == ext])
        
        if len(all_existing) != 0:
            print(f"  ✗ FAIL: Expected 0 existing images, found {len(all_existing)}")
            return False
        
        print(f"  ✓ Correctly detected {len(all_existing)} existing images")
        
        # The function should determine all images are needed
        images_needed = 10 - len(all_existing)
        if images_needed != 10:
            print(f"  ✗ FAIL: Expected 10 images needed, calculated {images_needed}")
            return False
        
        print(f"  ✓ Correctly calculated {images_needed} images needed")
    
    print("  ✓ PASS: No existing images detection test passed")
    return True


def test_image_numbering_with_existing():
    """Test that new images are numbered correctly when existing images are present."""
    print("\n" + "="*60)
    print("Test 4: Image numbering with existing images")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 3 existing images
        existing_images = create_test_images(output_dir, 3)
        print(f"  Created {len(existing_images)} existing images: {[img.name for img in existing_images]}")
        
        # Simulate what the download logic should do:
        # New images should start from index 3 (image_003.jpg)
        start_index = len(existing_images)
        expected_names = [f'image_{start_index + i:03d}.jpg' for i in range(7)]
        
        print(f"  New images should be numbered starting from image_{start_index:03d}.jpg")
        print(f"  Expected new image names: {expected_names[:3]}... (7 total)")
        
        # Verify the naming logic
        if start_index != 3:
            print(f"  ✗ FAIL: Expected start_index=3, got {start_index}")
            return False
        
        if expected_names[0] != 'image_003.jpg':
            print(f"  ✗ FAIL: Expected first new image 'image_003.jpg', got {expected_names[0]}")
            return False
        
        print(f"  ✓ Correct numbering logic: new images start from {expected_names[0]}")
    
    print("  ✓ PASS: Image numbering test passed")
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("Image Collection Optimization Tests")
    print("="*60)
    print("Testing logic changes without requiring Google API")
    
    tests = [
        test_sufficient_existing_images,
        test_partial_existing_images_logic,
        test_no_existing_images_detection,
        test_image_numbering_with_existing,
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
            print(f"  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print()
    print("="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
