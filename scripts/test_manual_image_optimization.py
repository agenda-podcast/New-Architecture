#!/usr/bin/env python3
"""
Manual test to demonstrate the image collection optimization.
This script shows the three scenarios:
1. No existing images
2. Some existing images (partial)
3. Sufficient existing images
"""
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))


def create_dummy_image(path: Path):
    """Create a dummy image file."""
    with open(path, 'wb') as f:
        f.write(b'FAKE_IMAGE_DATA' * 100)  # 1.5KB


def demo_scenario_1():
    """Scenario 1: No existing images - would need API call."""
    print("\n" + "="*70)
    print("SCENARIO 1: No Existing Images")
    print("="*70)
    
    from image_collector import collect_images_for_topic
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Directory: {output_dir}")
        print(f"Existing images: 0")
        print(f"Required images: 10")
        print(f"Expected behavior: Would call API to download 10 images")
        print(f"(Skipping actual API call in demo)")
        print()


def demo_scenario_2():
    """Scenario 2: Partial existing images - would need partial API call."""
    print("\n" + "="*70)
    print("SCENARIO 2: Partial Existing Images (5 out of 10)")
    print("="*70)
    
    from image_collector import collect_images_for_topic
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 5 existing images
        for i in range(5):
            create_dummy_image(output_dir / f'image_{i:03d}.jpg')
        
        print(f"Directory: {output_dir}")
        print(f"Existing images: 5")
        print(f"  - image_000.jpg through image_004.jpg")
        print(f"Required images: 10")
        print(f"Expected behavior: Would call API to download only 5 more images")
        print(f"  - New images would be named image_005.jpg through image_009.jpg")
        print(f"(Skipping actual API call in demo)")
        print()


def demo_scenario_3():
    """Scenario 3: Sufficient existing images - no API call needed."""
    print("\n" + "="*70)
    print("SCENARIO 3: Sufficient Existing Images")
    print("="*70)
    
    from image_collector import collect_images_for_topic
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 10 existing images
        for i in range(10):
            create_dummy_image(output_dir / f'image_{i:03d}.jpg')
        
        print(f"Directory: {output_dir}")
        print(f"Existing images: 10")
        print(f"  - image_000.jpg through image_009.jpg")
        print(f"Required images: 10")
        print(f"Expected behavior: NO API call - use existing images")
        print()
        print(f"Calling collect_images_for_topic()...")
        print()
        
        # This should return existing images without calling API
        try:
            result = collect_images_for_topic(
                topic_title="Demo Topic",
                topic_queries=["demo query"],
                output_dir=output_dir,
                num_images=10,
                api_key=None,  # No API key needed
                search_engine_id=None  # No search engine ID needed
            )
            
            print()
            print(f"✓ SUCCESS: Returned {len(result)} images without API call")
            print(f"  Images: {[img.name for img in result[:3]]}... (showing first 3)")
            
        except Exception as e:
            print(f"✗ ERROR: {e}")


def main():
    """Run all demo scenarios."""
    print("="*70)
    print("Image Collection Optimization Demo")
    print("="*70)
    print()
    print("This demo shows how the optimized image collection logic works:")
    print("1. Checks for existing images first")
    print("2. Returns existing images if sufficient (no API call)")
    print("3. Requests only needed images if partial collection exists")
    print("4. Numbers new images sequentially after existing ones")
    
    demo_scenario_1()
    demo_scenario_2()
    demo_scenario_3()
    
    print("\n" + "="*70)
    print("Demo Complete")
    print("="*70)
    print()
    print("Key Benefits:")
    print("  ✓ Saves API quota by reusing existing images")
    print("  ✓ Reduces latency by skipping unnecessary downloads")
    print("  ✓ Handles partial collections gracefully")
    print("  ✓ Preserves existing images during re-runs")
    print("="*70)


if __name__ == '__main__':
    main()
