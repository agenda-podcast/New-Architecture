#!/usr/bin/env python3
"""Test enabled topic filtering functionality."""
import json
import tempfile
import shutil
from pathlib import Path

try:
    from config import load_topic_config, get_enabled_topics, get_repo_root, is_topic_enabled
except ImportError as e:
    print(f"Error: Failed to import config module: {e}")
    print("Make sure you're running this from the scripts directory")
    import sys
    sys.exit(1)

# Constants
TOPIC_GLOB_PATTERN = 'topic-*.json'


def test_get_enabled_topics():
    """Test that get_enabled_topics correctly filters topics."""
    print("Testing get_enabled_topics()...")
    
    # Get the actual topics directory
    repo_root = get_repo_root()
    topics_dir = repo_root / 'topics'
    
    # Load all topics and check enabled status
    all_topics = []
    enabled_from_configs = []
    disabled_from_configs = []
    
    for topic_file in sorted(topics_dir.glob(TOPIC_GLOB_PATTERN)):
        topic_id = topic_file.stem
        all_topics.append(topic_id)
        
        config = load_topic_config(topic_id)
        if is_topic_enabled(config):
            enabled_from_configs.append(topic_id)
        else:
            disabled_from_configs.append(topic_id)
    
    # Get enabled topics using the utility function
    enabled_topics = get_enabled_topics()
    
    # Verify the function returns the same list as manual check
    assert set(enabled_topics) == set(enabled_from_configs), \
        f"Mismatch: get_enabled_topics()={enabled_topics} vs manual={enabled_from_configs}"
    
    # Verify disabled topics are not in the enabled list
    for disabled in disabled_from_configs:
        assert disabled not in enabled_topics, \
            f"Disabled topic {disabled} should not be in enabled list"
    
    print(f"✓ Found {len(all_topics)} total topics")
    print(f"✓ Found {len(enabled_topics)} enabled topics: {enabled_topics}")
    print(f"✓ Found {len(disabled_from_configs)} disabled topics: {disabled_from_configs}")
    print("✓ get_enabled_topics() works correctly!\n")


def test_disabled_topic_exclusion():
    """Test that disabled topics are properly excluded."""
    print("Testing disabled topic exclusion...")
    
    repo_root = get_repo_root()
    topics_dir = repo_root / 'topics'
    
    # Find a disabled topic
    disabled_topics = []
    for topic_file in sorted(topics_dir.glob(TOPIC_GLOB_PATTERN)):
        config = load_topic_config(topic_file.stem)
        if not is_topic_enabled(config):
            disabled_topics.append(config['id'])
    
    if not disabled_topics:
        print("⚠ No disabled topics found to test exclusion")
        return
    
    enabled_topics = get_enabled_topics()
    
    # Verify each disabled topic is not in the enabled list
    for disabled_topic in disabled_topics:
        assert disabled_topic not in enabled_topics, \
            f"Disabled topic {disabled_topic} should not be in enabled topics"
        print(f"✓ Topic {disabled_topic} properly excluded (enabled=false)")
    
    print("✓ All disabled topics are properly excluded!\n")


def test_default_enabled_behavior():
    """Test that topics without 'enabled' field default to True."""
    print("Testing default enabled behavior...")
    
    # Create a temporary topic config without 'enabled' field
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        topics_dir = tmpdir_path / 'topics'
        topics_dir.mkdir()
        
        # Create a test config without 'enabled' field
        test_config = {
            'id': 'topic-test',
            'title': 'Test Topic',
            'queries': ['test']
        }
        
        config_path = topics_dir / 'topic-test.json'
        with open(config_path, 'w') as f:
            json.dump(test_config, f, indent=2)
        
        # Load and verify it defaults to enabled
        with open(config_path, 'r') as f:
            loaded_config = json.load(f)
        
        # Test using the helper function
        assert is_topic_enabled(loaded_config) is True, "Topics without 'enabled' field should default to True"
        
        print("✓ Topics without 'enabled' field default to True (backward compatibility)")
        print("✓ Default enabled behavior works correctly!\n")


def main():
    """Run all tests."""
    print("=" * 70)
    print("ENABLED TOPICS FILTERING TESTS")
    print("=" * 70 + "\n")
    
    try:
        test_get_enabled_topics()
        test_disabled_topic_exclusion()
        test_default_enabled_behavior()
        
        print("=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
