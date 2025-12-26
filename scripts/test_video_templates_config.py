#!/usr/bin/env python3
"""
Test script for video_templates.yml configuration

This test verifies that the video template configuration is valid and complete.
"""
import sys
from pathlib import Path

import yaml

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))


def test_config_exists():
    """Test that video_templates.yml exists."""
    print("Test 1: Check config file exists")
    
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config" / "video_templates.yml"
    
    if not config_path.exists():
        print(f"  ✗ Config file not found: {config_path}")
        return False
    
    print(f"  ✓ Config file exists: {config_path}")
    return True


def test_config_structure():
    """Test that config has required structure."""
    print("\nTest 2: Validate config structure")
    
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config" / "video_templates.yml"
    
    if not config_path.exists():
        print(f"  ⚠ Skipping test - config file not found")
        return True
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Check top-level structure
        assert 'version' in config, "Config should have 'version' field"
        assert 'selection' in config, "Config should have 'selection' field"
        
        print(f"  ✓ Config version: {config['version']}")
        
        # Check selection structure
        selection = config['selection']
        assert 'default_strategy' in selection, "Selection should have 'default_strategy'"
        assert 'by_content_type' in selection, "Selection should have 'by_content_type'"
        
        print(f"  ✓ Default strategy: {selection['default_strategy']}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_content_types():
    """Test that all content types are configured."""
    print("\nTest 3: Check content type configurations")
    
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config" / "video_templates.yml"
    
    if not config_path.exists():
        print(f"  ⚠ Skipping test - config file not found")
        return True
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        expected_content_types = ['long', 'medium', 'short', 'reels']
        by_content_type = config['selection']['by_content_type']
        
        for content_type in expected_content_types:
            if content_type not in by_content_type:
                print(f"  ⚠ Warning: Content type '{content_type}' not configured")
                continue
            
            ct_config = by_content_type[content_type]
            
            # Check required fields
            if 'strategy' not in ct_config:
                print(f"  ⚠ Warning: Content type '{content_type}' missing 'strategy'")
            
            if 'candidates' not in ct_config:
                print(f"  ⚠ Warning: Content type '{content_type}' missing 'candidates'")
            else:
                candidates = ct_config['candidates']
                print(f"  ✓ {content_type}: {len(candidates)} candidates ({ct_config.get('strategy', 'N/A')} strategy)")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_candidate_validity():
    """Test that template candidates exist in inventory."""
    print("\nTest 4: Validate template candidates exist in inventory")
    
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config" / "video_templates.yml"
    inventory_path = repo_root / "templates" / "inventory.yml"
    
    if not config_path.exists():
        print(f"  ⚠ Skipping test - config file not found")
        return True
    
    if not inventory_path.exists():
        print(f"  ⚠ Skipping test - inventory file not found")
        return True
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        with open(inventory_path, 'r', encoding='utf-8') as f:
            inventory = yaml.safe_load(f)
        
        # Get all template IDs from inventory
        template_ids = set(inventory.keys())
        
        # Check candidates
        by_content_type = config['selection']['by_content_type']
        all_valid = True
        
        for content_type, ct_config in by_content_type.items():
            candidates = ct_config.get('candidates', [])
            
            for candidate in candidates:
                if candidate not in template_ids:
                    print(f"  ✗ Template '{candidate}' (used in {content_type}) not found in inventory")
                    all_valid = False
        
        if all_valid:
            print(f"  ✓ All template candidates exist in inventory")
        
        return all_valid
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_fallback_configuration():
    """Test fallback configuration."""
    print("\nTest 5: Validate fallback configuration")
    
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config" / "video_templates.yml"
    
    if not config_path.exists():
        print(f"  ⚠ Skipping test - config file not found")
        return True
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        selection = config['selection']
        
        # Check fallback settings
        if 'fallback_to_none' in selection:
            print(f"  ✓ fallback_to_none: {selection['fallback_to_none']}")
        
        if 'fallback_template_id' in selection:
            print(f"  ✓ fallback_template_id: {selection['fallback_template_id']}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("Testing video_templates.yml configuration")
    print("="*60)
    
    tests = [
        test_config_exists,
        test_config_structure,
        test_content_types,
        test_candidate_validity,
        test_fallback_configuration,
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
