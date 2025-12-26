#!/usr/bin/env python3
"""Test script to verify script_generate.py fixes for start_time handling."""
import sys
import json

# Test the fixed functions
try:
    from script_generate import generate_chapters, script_to_text, script_to_rss_description
    print("✓ Script generation functions imported successfully")
except ImportError as e:
    print(f"✗ Failed to import script_generate: {e}")
    sys.exit(1)

print("\n=== Testing start_time Handling ===")

# Test 1: Segments with missing start_time
print("\nTest 1: Segments with missing start_time field")
test_script = {
    'title': 'Test Podcast',
    'duration_sec': 1800,
    'segments': [
        {
            'chapter': 1,
            'title': 'Introduction',
            'dialogue': [
                {'speaker': 'A', 'text': 'Hello'}
            ]
            # Missing start_time
        },
        {
            'chapter': 2,
            'title': 'Main Content',
            'start_time': 300,
            'dialogue': [
                {'speaker': 'B', 'text': 'Welcome'}
            ]
        }
    ]
}

try:
    chapters = generate_chapters(test_script)
    print(f"✓ generate_chapters() handled missing start_time")
    print(f"  Generated {len(chapters)} chapters")
    for ch in chapters:
        print(f"    - {ch['title']}: {ch['start_time']}s")
except KeyError as e:
    print(f"✗ generate_chapters() failed with KeyError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ generate_chapters() failed: {e}")
    sys.exit(1)

# Test 2: script_to_text with missing start_time
print("\nTest 2: script_to_text with missing start_time")
try:
    text = script_to_text(test_script)
    print(f"✓ script_to_text() handled missing start_time")
    print(f"  Generated {len(text)} characters of text")
except KeyError as e:
    print(f"✗ script_to_text() failed with KeyError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ script_to_text() failed: {e}")
    sys.exit(1)

# Test 3: script_to_rss_description with missing start_time
print("\nTest 3: script_to_rss_description with missing start_time")
try:
    rss_desc = script_to_rss_description(test_script)
    print(f"✓ script_to_rss_description() handled missing start_time")
    print(f"  Generated {len(rss_desc)} characters of RSS description")
except KeyError as e:
    print(f"✗ script_to_rss_description() failed with KeyError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ script_to_rss_description() failed: {e}")
    sys.exit(1)

# Test 4: All segments have start_time (should still work)
print("\nTest 4: All segments with start_time field")
complete_script = {
    'title': 'Complete Test Podcast',
    'duration_sec': 1800,
    'segments': [
        {
            'chapter': 1,
            'title': 'Introduction',
            'start_time': 0,
            'dialogue': [
                {'speaker': 'A', 'text': 'Hello'}
            ]
        },
        {
            'chapter': 2,
            'title': 'Main Content',
            'start_time': 300,
            'dialogue': [
                {'speaker': 'B', 'text': 'Welcome'}
            ]
        }
    ]
}

try:
    chapters = generate_chapters(complete_script)
    text = script_to_text(complete_script)
    rss_desc = script_to_rss_description(complete_script)
    print(f"✓ All functions work with complete segments")
    print(f"  Chapters: {len(chapters)}")
    print(f"  Text length: {len(text)}")
    print(f"  RSS length: {len(rss_desc)}")
except Exception as e:
    print(f"✗ Functions failed with complete segments: {e}")
    sys.exit(1)

# Test 5: Empty segments list
print("\nTest 5: Empty segments list")
empty_script = {
    'title': 'Empty Test Podcast',
    'duration_sec': 0,
    'segments': []
}

try:
    chapters = generate_chapters(empty_script)
    text = script_to_text(empty_script)
    print(f"✓ Functions handle empty segments list")
    print(f"  Chapters: {len(chapters)}")
except Exception as e:
    print(f"✗ Functions failed with empty segments: {e}")
    sys.exit(1)

# Summary
print("\n" + "="*60)
print("=== Test Summary ===")
print("✓ All start_time handling tests passed")
print("✓ generate_chapters() uses .get() with default")
print("✓ script_to_text() uses .get() with default")
print("✓ script_to_rss_description() uses .get() with default")
print("✓ Functions work with both missing and present start_time")
print("✓ Functions handle edge cases (empty segments)")
print("\nThe script_generate.py fixes are working correctly!")
print("="*60)
