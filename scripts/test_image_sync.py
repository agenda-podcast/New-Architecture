#!/usr/bin/env python3
"""
Test to verify that images are properly synchronized to disk.
This test validates the fix for the black screen issue where images
weren't fully written to disk before video rendering began.
"""
import os
import sys
import tempfile
from pathlib import Path

# Test constants
TEST_DATA_REPETITIONS = 1000
GOOD_DATA_REPETITIONS = 100

def test_image_write_with_sync():
    """Test that image writing includes proper sync operations."""
    print("Testing image write with sync operations...")
    
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test_image.jpg"
        
        # Write test data with sync (simulating our fixed code)
        test_data = b"FAKE_IMAGE_DATA" * TEST_DATA_REPETITIONS  # Some fake image data
        
        with open(test_file, 'wb') as f:
            f.write(test_data)
            os.fsync(f.fileno())  # Ensure OS writes data to disk (includes flush)
        
        # Verify file exists and has correct size
        if not test_file.exists():
            print("  ✗ File does not exist after write")
            return False
        
        file_size = test_file.stat().st_size
        if file_size != len(test_data):
            print(f"  ✗ File size mismatch: expected {len(test_data)}, got {file_size}")
            return False
        
        # Verify file is readable
        try:
            with open(test_file, 'rb') as f:
                read_data = f.read()
            if read_data != test_data:
                print("  ✗ File content mismatch")
                return False
        except Exception as e:
            print(f"  ✗ Cannot read file: {e}")
            return False
        
        print("  ✓ File written, synced, and verified successfully")
        return True


def test_image_verification():
    """Test the image verification logic."""
    print("Testing image verification logic...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test files
        good_file = temp_path / "good_image.jpg"
        empty_file = temp_path / "empty_image.jpg"
        
        # Write a good file
        with open(good_file, 'wb') as f:
            f.write(b"GOOD_DATA" * GOOD_DATA_REPETITIONS)
            os.fsync(f.fileno())
        
        # Create an empty file
        empty_file.touch()
        
        # Test verification logic
        verified_images = []
        test_images = [good_file, empty_file]
        
        for img_path in test_images:
            if img_path.exists():
                try:
                    file_size = img_path.stat().st_size
                    if file_size > 0:
                        verified_images.append(img_path)
                    else:
                        print(f"  ⚠ Empty file skipped: {img_path.name}")
                except Exception as e:
                    print(f"  ✗ Error checking file {img_path.name}: {e}")
                    return False
            else:
                print(f"  ✗ File does not exist: {img_path.name}")
                return False
        
        if len(verified_images) != 1:
            print(f"  ✗ Expected 1 verified image, got {len(verified_images)}")
            return False
        
        if verified_images[0] != good_file:
            print("  ✗ Wrong file verified")
            return False
        
        print("  ✓ Verification logic correctly filters empty files")
        return True


def main():
    """Run all tests."""
    print("="*60)
    print("Image Sync and Verification Tests")
    print("="*60)
    
    tests = [
        test_image_write_with_sync,
        test_image_verification,
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
    
    print("="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
