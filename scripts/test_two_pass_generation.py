#!/usr/bin/env python3
"""
Test script for two-pass generation architecture.

This tests the structure and logic without making actual API calls.
"""
import json
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from responses_api_generator import (
    generate_pass_a_input,
    generate_pass_b_input,
    PASS_A_INSTRUCTIONS,
    PASS_B_INSTRUCTIONS,
    CANONICAL_PACK_TEMPLATE
)


def test_pass_a_input_generation():
    """Test that Pass A input is generated correctly."""
    print("Testing Pass A input generation...")
    
    hosts = {
        'host_a_name': 'Alex',
        'host_a_bio': 'Tech analyst with 15+ years experience',
        'host_b_name': 'Jessica',
        'host_b_bio': 'Fashion journalist and cultural observer'
    }
    
    input_text = generate_pass_a_input(
        topic="AI Safety Regulations",
        topic_description="Latest developments in AI safety and regulation",
        freshness_window="last 24 hours",
        region="US",
        rumors_allowed=True,
        l1_words=10000,
        hosts=hosts
    )
    
    # Validate structure
    assert "Topic: AI Safety Regulations" in input_text
    assert "Freshness window: last 24 hours" in input_text
    assert "Region: US" in input_text
    assert "Alex" in input_text
    assert "Jessica" in input_text
    assert "10000" in input_text
    assert "web_search" in input_text
    assert "sources" in input_text
    assert "canonical_pack" in input_text
    
    print("✓ Pass A input generation works correctly")
    print(f"  Input length: {len(input_text)} chars")
    return True


def test_pass_b_input_generation():
    """Test that Pass B input is generated correctly."""
    print("\nTesting Pass B input generation...")
    
    canonical_pack = {
        "timeline": "Jan 1: Event A; Jan 2: Event B",
        "key_facts": "Fact 1, Fact 2, Fact 3",
        "key_players": "Person A, Company B, Organization C",
        "claims_evidence": "Claim X supported by Source Y",
        "beats_outline": "Beat 1, Beat 2, Beat 3, Beat 4, Beat 5",
        "punchlines": "Witty quote 1, Memorable line 2"
    }
    
    input_text = generate_pass_b_input(
        canonical_pack=canonical_pack,
        m_words=2500,
        s_words=1000,
        r_words=80,
        medium_enabled=True,
        short_enabled=True,
        reels_enabled=True
    )
    
    # Validate structure
    assert "CANONICAL_PACK" in input_text
    assert "M1-M2" in input_text or "M:" in input_text  # Medium format mentioned
    assert "S1-S4" in input_text or "S:" in input_text  # Short format mentioned
    assert "R1-R8" in input_text or "R:" in input_text  # Reels format mentioned
    assert "2500" in input_text
    assert "1000" in input_text
    assert "80" in input_text
    assert "Event A" in input_text  # From canonical pack
    
    print("✓ Pass B input generation works correctly")
    print(f"  Input length: {len(input_text)} chars")
    return True


def test_instructions_content():
    """Test that instructions contain critical elements."""
    print("\nTesting instruction templates...")
    
    # Pass A must have web search instructions
    assert "web_search" in PASS_A_INSTRUCTIONS
    assert "knowledge cutoff" in PASS_A_INSTRUCTIONS.lower()
    assert "Never say you cannot browse" in PASS_A_INSTRUCTIONS
    assert "sources within the window are limited" in PASS_A_INSTRUCTIONS
    assert "canonical_pack" in PASS_A_INSTRUCTIONS
    
    # Pass A must have historical context instructions
    assert "historical context" in PASS_A_INSTRUCTIONS.lower() or "Historical Context" in PASS_A_INSTRUCTIONS
    assert "EXISTING KNOWLEDGE" in PASS_A_INSTRUCTIONS or "existing knowledge" in PASS_A_INSTRUCTIONS
    
    print("✓ Pass A instructions contain all required elements (including historical context)")
    
    # Pass B must prohibit new facts
    assert "Do not add new facts" in PASS_B_INSTRUCTIONS
    assert "CANONICAL_PACK" in PASS_B_INSTRUCTIONS
    assert "M1–M2" in PASS_B_INSTRUCTIONS
    assert "S1–S4" in PASS_B_INSTRUCTIONS
    assert "R1–R8" in PASS_B_INSTRUCTIONS
    
    # Pass B should reference historical context
    assert "historical" in PASS_B_INSTRUCTIONS.lower()
    
    print("✓ Pass B instructions contain all required elements (including historical context)")
    return True


def test_canonical_pack_structure():
    """Test that canonical pack template has required fields."""
    print("\nTesting canonical pack structure...")
    
    required_fields = [
        "timeline",
        "key_facts",
        "key_players",
        "claims_evidence",
        "beats_outline",
        "punchlines",
        "historical_context"
    ]
    
    for field in required_fields:
        assert field in CANONICAL_PACK_TEMPLATE, f"Missing field: {field}"
    
    print("✓ Canonical pack has all required fields:")
    for field in required_fields:
        print(f"  - {field}")
    
    return True


def test_output_format():
    """Test expected output format descriptions."""
    print("\nTesting output format expectations...")
    
    # Pass A should output: sources, canonical_pack, content[L1]
    assert "sources:" in PASS_A_INSTRUCTIONS
    assert "canonical_pack:" in PASS_A_INSTRUCTIONS
    assert "content:" in PASS_A_INSTRUCTIONS
    assert "L1" in PASS_A_INSTRUCTIONS
    
    print("✓ Pass A expects correct output format")
    
    # Pass B should output: content[M1-M2, S1-S4, R1-R8]
    assert '{ "content":' in PASS_B_INSTRUCTIONS
    assert 'code:"M1"' in PASS_B_INSTRUCTIONS or "code:\"M1\"" in PASS_B_INSTRUCTIONS
    assert 'code:"R8"' in PASS_B_INSTRUCTIONS or "code:\"R8\"" in PASS_B_INSTRUCTIONS
    
    print("✓ Pass B expects correct output format")
    return True


def main():
    """Run all tests."""
    print("=" * 80)
    print("TWO-PASS GENERATION STRUCTURE TESTS")
    print("=" * 80)
    
    tests = [
        test_pass_a_input_generation,
        test_pass_b_input_generation,
        test_instructions_content,
        test_canonical_pack_structure,
        test_output_format
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"✗ Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ Test error: {e}")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
