#!/usr/bin/env python3
"""Test script parser functionality."""
import sys
import json
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from script_parser import (
    parse_script_text_to_segments,
    parse_script_text_to_multi_segments,
    convert_content_script_to_segments,
    validate_segments
)


def test_basic_parsing():
    """Test basic script text parsing."""
    print("Test 1: Basic script parsing")
    print("=" * 60)
    
    script_text = """HOST_A: Welcome to the show!
HOST_B: Thanks for having me!
HOST_A: Let's dive into the topic.
HOST_B: Sounds great!"""
    
    segments = parse_script_text_to_segments(script_text)
    
    assert len(segments) == 1, f"Expected 1 segment, got {len(segments)}"
    assert len(segments[0]['dialogue']) == 4, f"Expected 4 dialogue items, got {len(segments[0]['dialogue'])}"
    assert segments[0]['dialogue'][0]['speaker'] == 'A'
    assert segments[0]['dialogue'][1]['speaker'] == 'B'
    assert 'Welcome to the show!' in segments[0]['dialogue'][0]['text']
    
    print(f"✓ Parsed {len(segments[0]['dialogue'])} dialogue items")
    print(f"  First item: {segments[0]['dialogue'][0]}")
    print()
    return True


def test_empty_script():
    """Test handling of empty script."""
    print("Test 2: Empty script handling")
    print("=" * 60)
    
    segments = parse_script_text_to_segments("")
    
    assert len(segments) == 0, f"Expected 0 segments for empty script, got {len(segments)}"
    
    print("✓ Correctly handled empty script")
    print()
    return True


def test_no_markers():
    """Test script with no HOST markers."""
    print("Test 3: Script with no HOST markers")
    print("=" * 60)
    
    script_text = "Just some text without any markers."
    segments = parse_script_text_to_segments(script_text)
    
    assert len(segments) == 0, f"Expected 0 segments for unmarked text, got {len(segments)}"
    
    print("✓ Correctly handled unmarked text")
    print()
    return True


def test_multi_segment_parsing():
    """Test parsing into multiple segments."""
    print("Test 4: Multi-segment parsing")
    print("=" * 60)
    
    # Create a long script with many dialogue items
    dialogue_items = []
    for i in range(150):  # 150 dialogue items
        speaker = 'A' if i % 2 == 0 else 'B'
        dialogue_items.append(f"HOST_{speaker}: Item {i+1}")
    
    script_text = '\n'.join(dialogue_items)
    
    segments = parse_script_text_to_multi_segments(script_text, target_dialogues_per_segment=50)
    
    assert len(segments) == 3, f"Expected 3 segments for 150 items, got {len(segments)}"
    
    total_dialogue = sum(len(seg['dialogue']) for seg in segments)
    assert total_dialogue == 150, f"Expected 150 total dialogue, got {total_dialogue}"
    
    print(f"✓ Split 150 dialogue items into {len(segments)} segments")
    print(f"  Segment 1: {len(segments[0]['dialogue'])} items")
    print(f"  Segment 2: {len(segments[1]['dialogue'])} items")
    print(f"  Segment 3: {len(segments[2]['dialogue'])} items")
    print()
    return True


def test_content_conversion():
    """Test converting content item from script to segments."""
    print("Test 5: Content item conversion")
    print("=" * 60)
    
    content_item = {
        'code': 'R1',
        'type': 'reels',
        'target_words': 80,
        'script': 'HOST_A: Breaking news! HOST_B: Tell us more! HOST_A: This is amazing! HOST_B: Indeed!'
    }
    
    # Convert
    converted = convert_content_script_to_segments(content_item)
    
    assert 'segments' in converted, "Converted item should have 'segments' field"
    assert len(converted['segments']) > 0, "Should have at least one segment"
    assert len(converted['segments'][0]['dialogue']) == 4, f"Expected 4 dialogue items, got {len(converted['segments'][0]['dialogue'])}"
    
    print(f"✓ Converted script to {len(converted['segments'])} segment(s)")
    print(f"  Dialogue count: {len(converted['segments'][0]['dialogue'])}")
    print()
    return True


def test_validation():
    """Test segment validation."""
    print("Test 6: Segment validation")
    print("=" * 60)
    
    # Valid segments
    valid_segments = [
        {
            'chapter': 1,
            'title': 'Test',
            'dialogue': [
                {'speaker': 'A', 'text': 'Hello'},
                {'speaker': 'B', 'text': 'Hi'}
            ]
        }
    ]
    
    assert validate_segments(valid_segments, 'TEST'), "Valid segments should pass validation"
    print("✓ Valid segments passed validation")
    
    # Invalid: empty segments
    assert not validate_segments([], 'TEST'), "Empty segments should fail validation"
    print("✓ Empty segments failed validation as expected")
    
    # Invalid: no dialogue
    invalid_segments = [{'chapter': 1, 'title': 'Test', 'dialogue': []}]
    assert not validate_segments(invalid_segments, 'TEST'), "Segments without dialogue should fail"
    print("✓ Segments without dialogue failed validation as expected")
    
    print()
    return True


def test_real_mock_data():
    """Test with real mock data from pass_b_response.json."""
    print("Test 7: Real mock data parsing")
    print("=" * 60)
    
    # Load mock data
    mock_file = Path(__file__).parent.parent / 'test_data' / 'mock_responses' / 'pass_b_response.json'
    
    if not mock_file.exists():
        print(f"⚠ Mock file not found: {mock_file}")
        print("  Skipping this test")
        print()
        return True
    
    with open(mock_file, 'r') as f:
        mock_data = json.load(f)
    
    content_list = mock_data.get('content', [])
    
    if not content_list:
        print("⚠ No content in mock data")
        print()
        return True
    
    print(f"Found {len(content_list)} content items in mock data")
    
    success_count = 0
    for content_item in content_list:
        code = content_item.get('code', 'UNKNOWN')
        
        # Convert script to segments
        converted = convert_content_script_to_segments(content_item.copy())
        
        segments = converted.get('segments', [])
        if segments and validate_segments(segments, code):
            total_dialogue = sum(len(seg.get('dialogue', [])) for seg in segments)
            print(f"  ✓ {code}: {len(segments)} segment(s), {total_dialogue} dialogue items")
            success_count += 1
        else:
            print(f"  ✗ {code}: Failed to parse or validate")
    
    print(f"\nSuccessfully parsed {success_count}/{len(content_list)} content items")
    print()
    return success_count == len(content_list)


if __name__ == '__main__':
    print("=" * 60)
    print("Script Parser Tests")
    print("=" * 60)
    print()
    
    tests = [
        test_basic_parsing,
        test_empty_script,
        test_no_markers,
        test_multi_segment_parsing,
        test_content_conversion,
        test_validation,
        test_real_mock_data,
    ]
    
    results = []
    for test_func in tests:
        try:
            results.append(test_func())
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed")
        sys.exit(1)
