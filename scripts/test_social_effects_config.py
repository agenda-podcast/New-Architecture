#!/usr/bin/env python3
"""
Unit test for social effects configuration.

Tests that the new configuration options are properly set and can be imported.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def test_global_config_imports():
    """Test that new config options can be imported."""
    print("\n" + "="*60)
    print("TEST: Global Config Imports")
    print("="*60)
    
    try:
        from global_config import (
            ENABLE_SOCIAL_EFFECTS,
            SOCIAL_EFFECTS_STYLE
        )
        
        print(f"✓ ENABLE_SOCIAL_EFFECTS imported: {ENABLE_SOCIAL_EFFECTS}")
        print(f"✓ SOCIAL_EFFECTS_STYLE imported: {SOCIAL_EFFECTS_STYLE}")
        
        # Verify types
        if not isinstance(ENABLE_SOCIAL_EFFECTS, bool):
            print(f"✗ ENABLE_SOCIAL_EFFECTS should be bool, got {type(ENABLE_SOCIAL_EFFECTS)}")
            return False
        
        if not isinstance(SOCIAL_EFFECTS_STYLE, str):
            print(f"✗ SOCIAL_EFFECTS_STYLE should be str, got {type(SOCIAL_EFFECTS_STYLE)}")
            return False
        
        # Verify valid values
        valid_styles = ['auto', 'none', 'safe', 'cinematic', 'experimental']
        if SOCIAL_EFFECTS_STYLE not in valid_styles:
            print(f"⚠ Warning: SOCIAL_EFFECTS_STYLE='{SOCIAL_EFFECTS_STYLE}' not in {valid_styles}")
        
        print("✓ Config types are correct")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import config: {e}")
        return False


def test_image_collector_params():
    """Test that Google CSE parameters are correctly configured."""
    print("\n" + "="*60)
    print("TEST: Image Collector Google CSE Parameters")
    print("="*60)
    
    try:
        # Read the image_collector.py file and check for imgType parameter
        collector_path = Path(__file__).parent / 'image_collector.py'
        
        if not collector_path.exists():
            print(f"✗ image_collector.py not found at {collector_path}")
            return False
        
        with open(collector_path, 'r') as f:
            content = f.read()
        
        # Check for required parameters
        checks = [
            ("searchType='image'", "searchType parameter"),
            ("imgType='photo'", "imgType parameter"),
            ("safe='active'", "safe search parameter"),
        ]
        
        for pattern, description in checks:
            if pattern in content:
                print(f"✓ Found {description}: {pattern}")
            else:
                print(f"✗ Missing {description}: {pattern}")
                return False
        
        print("✓ All Google CSE parameters are correctly configured")
        return True
        
    except Exception as e:
        print(f"✗ Error checking image_collector.py: {e}")
        return False


def test_video_render_imports():
    """Test that video_render.py can import the new config options."""
    print("\n" + "="*60)
    print("TEST: Video Render Module Imports")
    print("="*60)
    
    try:
        # Check that video_render.py imports new config
        render_path = Path(__file__).parent / 'video_render.py'
        
        if not render_path.exists():
            print(f"✗ video_render.py not found at {render_path}")
            return False
        
        with open(render_path, 'r') as f:
            content = f.read()
        
        # Check for imports
        checks = [
            ("ENABLE_SOCIAL_EFFECTS", "ENABLE_SOCIAL_EFFECTS import"),
            ("SOCIAL_EFFECTS_STYLE", "SOCIAL_EFFECTS_STYLE import"),
            ("get_image_dimensions", "get_image_dimensions function"),
            ("create_blurred_background_composite", "create_blurred_background_composite function"),
            ("process_images_for_video", "process_images_for_video function"),
        ]
        
        for pattern, description in checks:
            if pattern in content:
                print(f"✓ Found {description}")
            else:
                print(f"✗ Missing {description}")
                return False
        
        print("✓ All required functions and imports are present")
        return True
        
    except Exception as e:
        print(f"✗ Error checking video_render.py: {e}")
        return False


def test_template_selector_integration():
    """Test that template selector can be imported and used."""
    print("\n" + "="*60)
    print("TEST: Template Selector Integration")
    print("="*60)
    
    try:
        import sys
        blender_dir = Path(__file__).parent / 'blender'
        sys.path.insert(0, str(blender_dir))
        
        from template_selector import TemplateSelector, generate_deterministic_seed
        
        print("✓ TemplateSelector imported successfully")
        
        # Test seed generation
        seed = generate_deterministic_seed('topic-01', '20251220', 'L1')
        print(f"✓ Generated deterministic seed: {seed}")
        
        if not isinstance(seed, str) or len(seed) != 12:
            print(f"✗ Seed should be 12-character string, got: {seed}")
            return False
        
        print("✓ Template selector integration test passed")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import template_selector: {e}")
        return False
    except Exception as e:
        print(f"✗ Error testing template selector: {e}")
        return False


def main():
    """Run all tests."""
    print("Testing Social Effects Configuration")
    print("="*60)
    
    tests = [
        ("Global Config Imports", test_global_config_imports),
        ("Image Collector Parameters", test_image_collector_params),
        ("Video Render Imports", test_video_render_imports),
        ("Template Selector Integration", test_template_selector_integration),
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
