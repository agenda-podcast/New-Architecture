#!/usr/bin/env python3
"""
Test script for ensure_blender_templates.py

This test verifies that the template verification and download script works correctly.
"""
import sys
import tempfile
import shutil
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ensure_blender_templates import (
    load_inventory,
    expected_files,
    check_missing,
)


def test_load_inventory():
    """Test loading inventory file."""
    print("Test 1: Load inventory file")
    
    # Use the actual inventory file from the repo
    repo_root = Path(__file__).parent.parent
    inventory_path = repo_root / "templates" / "inventory.yml"
    
    if not inventory_path.exists():
        print(f"  ⚠ Skipping test - inventory file not found: {inventory_path}")
        return True
    
    try:
        inventory = load_inventory(inventory_path)
        
        # Basic validations
        assert isinstance(inventory, dict), "Inventory should be a dictionary"
        assert len(inventory) > 0, "Inventory should not be empty"
        
        # Check that some expected templates exist
        expected_templates = ['minimal', 'neutral', 'clean']
        for template_id in expected_templates:
            if template_id in inventory:
                print(f"  ✓ Found expected template: {template_id}")
        
        print(f"  ✓ Loaded {len(inventory)} entries from inventory")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_expected_files():
    """Test extracting expected files from inventory."""
    print("\nTest 2: Extract expected files from inventory")
    
    repo_root = Path(__file__).parent.parent
    inventory_path = repo_root / "templates" / "inventory.yml"
    
    if not inventory_path.exists():
        print(f"  ⚠ Skipping test - inventory file not found: {inventory_path}")
        return True
    
    try:
        inventory = load_inventory(inventory_path)
        
        # Test with previews not required (default)
        files_no_previews = expected_files(repo_root, inventory, require_previews=False)
        
        # Test with previews required
        files_with_previews = expected_files(repo_root, inventory, require_previews=True)
        
        assert isinstance(files_no_previews, list), "Expected files should be a list"
        assert isinstance(files_with_previews, list), "Expected files should be a list"
        
        # When previews are required, we should have more files
        assert len(files_with_previews) >= len(files_no_previews), \
            "Files with previews should be >= files without previews"
        
        # Check that .blend files are included in both
        blend_files_no_previews = [f for f in files_no_previews if f.suffix == '.blend']
        blend_files_with_previews = [f for f in files_with_previews if f.suffix == '.blend']
        
        # Both should have same number of .blend files
        assert len(blend_files_no_previews) == len(blend_files_with_previews), \
            "Both should have same number of .blend files"
        
        print(f"  ✓ Found {len(blend_files_no_previews)} .blend files in inventory")
        
        # Check for preview files
        preview_files = [f for f in files_with_previews if f.suffix in ['.jpg', '.png']]
        print(f"  ✓ Found {len(preview_files)} preview files when require_previews=True")
        
        # Check for duplicates
        unique_files = set(files_no_previews)
        assert len(unique_files) == len(files_no_previews), "Files list should not contain duplicates"
        print(f"  ✓ No duplicate files in list")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_check_missing():
    """Test checking for missing files."""
    print("\nTest 3: Check for missing files")
    
    try:
        # Create a temporary directory with some files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create some test files
            file1 = tmpdir_path / "exists.txt"
            file1.write_text("test")
            
            # Check which files are missing
            test_files = [
                file1,  # exists
                tmpdir_path / "missing.txt",  # doesn't exist
            ]
            
            missing = check_missing(test_files)
            
            assert len(missing) == 1, "Should find exactly 1 missing file"
            assert missing[0].name == "missing.txt", "Should identify the correct missing file"
            
            print(f"  ✓ Correctly identified {len(missing)} missing file(s)")
            return True
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_inventory_structure():
    """Test that inventory has required structure."""
    print("\nTest 4: Validate inventory structure")
    
    repo_root = Path(__file__).parent.parent
    inventory_path = repo_root / "templates" / "inventory.yml"
    
    if not inventory_path.exists():
        print(f"  ⚠ Skipping test - inventory file not found: {inventory_path}")
        return True
    
    try:
        inventory = load_inventory(inventory_path)
        
        # Check that templates have required fields
        required_fields = ['name', 'category', 'description', 'path']
        
        checked_templates = 0
        for template_id, template_data in inventory.items():
            if not isinstance(template_data, dict):
                continue
                
            # Skip special entries like 'selection_weights', 'constraints', etc.
            if template_id in ['selection_weights', 'constraints']:
                continue
            
            checked_templates += 1
            
            # Check required fields
            for field in required_fields:
                if field not in template_data:
                    print(f"  ⚠ Warning: Template '{template_id}' missing field '{field}'")
        
        print(f"  ✓ Checked structure of {checked_templates} templates")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_non_selectable_templates_skipped():
    """Test that non-selectable templates are skipped."""
    print("\nTest 5: Non-selectable templates are skipped")
    
    repo_root = Path(__file__).parent.parent
    inventory_path = repo_root / "templates" / "inventory.yml"
    
    if not inventory_path.exists():
        print(f"  ⚠ Skipping test - inventory file not found: {inventory_path}")
        return True
    
    try:
        inventory = load_inventory(inventory_path)
        files = expected_files(repo_root, inventory, require_previews=False)
        
        # Find any non-selectable templates in inventory
        non_selectable_templates = []
        for template_id, template_data in inventory.items():
            if not isinstance(template_data, dict):
                continue
            if template_id in ['selection_weights', 'constraints']:
                continue
                
            if not template_data.get("selectable", True):
                non_selectable_templates.append((template_id, template_data.get("path")))
        
        if non_selectable_templates:
            # Check that none of the non-selectable templates are in expected files
            # Resolve paths for reliable comparison across platforms
            # Use set for O(1) lookup performance
            resolved_files = {f.resolve() for f in files}
            
            for template_id, template_path in non_selectable_templates:
                if template_path:
                    full_path = (repo_root / template_path).resolve()
                    if full_path in resolved_files:
                        print(f"  ✗ Error: Non-selectable template '{template_id}' is in expected files")
                        return False
                    else:
                        print(f"  ✓ Non-selectable template '{template_id}' correctly excluded")
        else:
            print(f"  ⚠ No non-selectable templates found in inventory")
        
        # Count selectable vs non-selectable templates
        selectable_count = 0
        non_selectable_count = 0
        
        for template_id, template_data in inventory.items():
            if not isinstance(template_data, dict):
                continue
            if template_id in ['selection_weights', 'constraints']:
                continue
                
            if template_data.get("selectable", True):
                selectable_count += 1
            else:
                non_selectable_count += 1
        
        print(f"  ✓ Found {selectable_count} selectable templates")
        print(f"  ✓ Found {non_selectable_count} non-selectable templates")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("Testing ensure_blender_templates.py")
    print("="*60)
    
    tests = [
        test_load_inventory,
        test_expected_files,
        test_check_missing,
        test_inventory_structure,
        test_non_selectable_templates_skipped,
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
