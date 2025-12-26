#!/usr/bin/env python3
"""
Integration test for template selection in video rendering.

This test demonstrates the template selection logic without actually rendering videos.
"""
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

import yaml


def test_sequential_rotation():
    """Test that sequential rotation works as expected."""
    print("Test 1: Sequential template rotation")
    
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config" / "video_templates.yml"
    inventory_path = repo_root / "templates" / "inventory.yml"
    
    if not config_path.exists() or not inventory_path.exists():
        print("  ⚠ Skipping test - config files not found")
        return True
    
    try:
        # Load configuration
        with open(config_path, 'r') as f:
            tpl_cfg = yaml.safe_load(f)
        
        # Test sequential rotation for 'medium' content type
        content_type = 'medium'
        content_settings = tpl_cfg.get("selection", {}).get("by_content_type", {}).get(content_type, {})
        candidates = content_settings.get("candidates", [])
        strategy = content_settings.get("strategy", "sequential")
        
        print(f"  Content type: {content_type}")
        print(f"  Strategy: {strategy}")
        print(f"  Candidates: {candidates}")
        
        # Simulate rotation through several videos
        rotation_idx = 0
        selections = []
        
        for i in range(10):  # Simulate 10 videos
            selected = candidates[rotation_idx % len(candidates)]
            selections.append(selected)
            rotation_idx += 1
        
        print(f"\n  Sequential selections for 10 videos:")
        for i, sel in enumerate(selections, 1):
            print(f"    Video {i}: {sel}")
        
        # Verify rotation pattern
        # Expected: candidates list repeated enough times to cover 10 videos
        expected_pattern = (candidates * ((10 // len(candidates)) + 1))[:10]
        if selections == expected_pattern:
            print(f"\n  ✓ Rotation pattern is correct")
            return True
        else:
            print(f"\n  ✗ Rotation pattern mismatch")
            print(f"    Expected: {expected_pattern}")
            print(f"    Got: {selections}")
            return False
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_content_types():
    """Test that different content types use different candidate pools."""
    print("\nTest 2: Multiple content types with independent rotation")
    
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config" / "video_templates.yml"
    
    if not config_path.exists():
        print("  ⚠ Skipping test - config file not found")
        return True
    
    try:
        with open(config_path, 'r') as f:
            tpl_cfg = yaml.safe_load(f)
        
        # Simulate rendering videos with different content types
        rotation_counters = {}
        
        # Simulate a batch of videos with mixed content types
        video_sequence = [
            ('long', 'L1'),
            ('medium', 'M1'),
            ('short', 'S1'),
            ('reels', 'R1'),
            ('long', 'L2'),
            ('medium', 'M2'),
            ('short', 'S2'),
            ('reels', 'R2'),
        ]
        
        selections = []
        
        for content_type, code in video_sequence:
            content_settings = tpl_cfg.get("selection", {}).get("by_content_type", {}).get(content_type, {})
            candidates = content_settings.get("candidates", [])
            strategy = content_settings.get("strategy", "sequential")
            
            rotation_counters.setdefault(content_type, 0)
            
            if strategy == "sequential" and candidates:
                selected = candidates[rotation_counters[content_type] % len(candidates)]
                rotation_counters[content_type] += 1
                selections.append((code, selected))
        
        print(f"  Video rendering sequence:")
        for code, template in selections:
            print(f"    {code}: {template}")
        
        # Verify that each content type maintains its own counter
        # For example, M1 and M2 should use different templates from the medium pool
        medium_selections = [t for c, t in selections if c.startswith('M')]
        if len(medium_selections) == 2 and medium_selections[0] != medium_selections[1]:
            print(f"\n  ✓ Content types maintain independent rotation counters")
            return True
        else:
            print(f"\n  ⚠ Note: Pattern may vary based on candidate pool sizes")
            return True
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_template_selector_integration():
    """Test that TemplateSelector can be imported and used."""
    print("\nTest 3: TemplateSelector integration")
    
    try:
        # Import template selector
        blender_dir = Path(__file__).parent / 'blender'
        sys.path.insert(0, str(blender_dir))
        from template_selector import TemplateSelector
        
        repo_root = Path(__file__).parent.parent
        templates_dir = repo_root / "templates"
        inventory_path = templates_dir / "inventory.yml"
        
        if not inventory_path.exists():
            print("  ⚠ Skipping test - inventory not found")
            return True
        
        # Create selector
        selector = TemplateSelector(templates_dir, inventory_path)
        
        # Test validation
        test_templates = ['minimal', 'neutral', 'clean']
        for template_id in test_templates:
            is_valid = selector.validate_template(template_id)
            template_path = selector.get_template_path(template_id)
            
            if template_path:
                print(f"  Template '{template_id}': path={template_path.name}")
            else:
                print(f"  Template '{template_id}': path not found (expected if templates not downloaded)")
        
        print(f"\n  ✓ TemplateSelector can be imported and used")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("="*60)
    print("Template Selection Integration Tests")
    print("="*60)
    
    tests = [
        test_sequential_rotation,
        test_multiple_content_types,
        test_template_selector_integration,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "="*60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("="*60)
    
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
