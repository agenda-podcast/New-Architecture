#!/usr/bin/env python3
"""
Test script to verify the new tagged format parsing.
This tests the single-request approach with XML-style tags.
"""
import json
from multi_format_generator import parse_multi_format_response


def test_tagged_format_parsing():
    """Test parsing of new tagged format response."""
    print("Testing tagged format parsing...")
    
    # Sample tagged response
    sample_response = """
<CONTENT_START>
<SCRIPT code="L1" type="long">
{
  "code": "L1",
  "type": "long",
  "target_duration": 3600,
  "segments": [
    {
      "chapter": 1,
      "title": "Introduction",
      "dialogue": [
        {"speaker": "A", "text": "Welcome to our podcast!"},
        {"speaker": "B", "text": "Thanks for having me!"}
      ]
    }
  ]
}
</SCRIPT>

<SCRIPT code="M1" type="medium">
{
  "code": "M1",
  "type": "medium",
  "target_duration": 900,
  "segments": [
    {
      "chapter": 1,
      "title": "Main Topic",
      "dialogue": [
        {"speaker": "A", "text": "Let's discuss the key points."},
        {"speaker": "B", "text": "Absolutely, great idea."}
      ]
    }
  ]
}
</SCRIPT>
<CONTENT_END>
"""
    
    try:
        # Parse the response
        result = parse_multi_format_response(sample_response)
        
        # Verify structure
        assert 'content' in result, "Result should have 'content' key"
        assert len(result['content']) == 2, f"Expected 2 scripts, got {len(result['content'])}"
        
        # Verify first script
        script1 = result['content'][0]
        assert script1['code'] == 'L1', f"First script code should be 'L1', got {script1['code']}"
        assert script1['type'] == 'long', f"First script type should be 'long', got {script1['type']}"
        assert len(script1['segments']) == 1, f"First script should have 1 segment"
        
        # Verify second script
        script2 = result['content'][1]
        assert script2['code'] == 'M1', f"Second script code should be 'M1', got {script2['code']}"
        assert script2['type'] == 'medium', f"Second script type should be 'medium', got {script2['type']}"
        
        print("✓ Tagged format parsing test passed")
        print(f"  - Successfully parsed {len(result['content'])} scripts")
        print(f"  - Script codes: {[s['code'] for s in result['content']]}")
        return True
        
    except Exception as e:
        print(f"✗ Tagged format parsing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_legacy_json_parsing():
    """Test that legacy JSON format still works."""
    print("\nTesting legacy JSON format parsing...")
    
    # Sample legacy response
    sample_response = """{
  "content": [
    {
      "code": "L1",
      "type": "long",
      "target_duration": 3600,
      "segments": [
        {
          "chapter": 1,
          "title": "Introduction",
          "dialogue": [
            {"speaker": "A", "text": "Welcome!"}
          ]
        }
      ]
    }
  ]
}"""
    
    try:
        # Parse the response
        result = parse_multi_format_response(sample_response)
        
        # Verify structure
        assert 'content' in result, "Result should have 'content' key"
        assert len(result['content']) == 1, f"Expected 1 script, got {len(result['content'])}"
        
        script1 = result['content'][0]
        assert script1['code'] == 'L1', f"Script code should be 'L1', got {script1['code']}"
        
        print("✓ Legacy JSON format parsing test passed")
        print(f"  - Successfully parsed {len(result['content'])} script")
        return True
        
    except Exception as e:
        print(f"✗ Legacy JSON format parsing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_malformed_tagged_format():
    """Test handling of malformed tagged format."""
    print("\nTesting malformed tagged format handling...")
    
    # Sample with one valid and one invalid script
    sample_response = """
<SCRIPT code="L1" type="long">
{
  "code": "L1",
  "type": "long",
  "segments": []
}
</SCRIPT>

<SCRIPT code="M1" type="medium">
{ INVALID JSON HERE
</SCRIPT>
"""
    
    try:
        # Parse the response - should get at least the valid one
        result = parse_multi_format_response(sample_response)
        
        assert 'content' in result, "Result should have 'content' key"
        assert len(result['content']) >= 1, "Should parse at least one valid script"
        
        print("✓ Malformed format handling test passed")
        print(f"  - Recovered {len(result['content'])} valid script(s) from malformed input")
        return True
        
    except Exception as e:
        print(f"✗ Malformed format handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("Tagged Format Parsing Tests")
    print("=" * 60)
    
    results = []
    results.append(test_tagged_format_parsing())
    results.append(test_legacy_json_parsing())
    results.append(test_malformed_tagged_format())
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All tests passed!")
        exit(0)
    else:
        print("\n✗ Some tests failed")
        exit(1)
