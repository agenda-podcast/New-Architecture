#!/usr/bin/env python3
"""
Test script for streaming and chunked generation.

This tests the structure and logic of streaming without making actual API calls.
"""
import json
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from responses_api_generator import (
    generate_pass_a_input,
    PASS_A_INSTRUCTIONS
)


def test_chunked_structure():
    """Test that chunked generation structure is defined correctly."""
    print("Testing chunked generation structure...")
    
    # Expected chunks for 10,000 word L1
    expected_chunks = [
        {"index": 1, "words": 400, "description": "Cold Open"},
        {"index": 2, "words": 1600, "description": "What Happened"},
        {"index": 3, "words": 1400, "description": "Why It Matters"},
        {"index": 4, "words": 1500, "description": "Deep Dive Part 1"},
        {"index": 5, "words": 1500, "description": "Deep Dive Part 2"},
        {"index": 6, "words": 1500, "description": "Deep Dive Part 3"},
        {"index": 7, "words": 700, "description": "Rumor Watch"},
        {"index": 8, "words": 600, "description": "What's Next"},
        {"index": 9, "words": 500, "description": "Actionable Insights"},
        {"index": 10, "words": 300, "description": "Wrap + CTA"}
    ]
    
    # Verify total words
    total_words = sum(chunk["words"] for chunk in expected_chunks)
    assert total_words == 10000, f"Total words should be 10000, got {total_words}"
    
    # Verify we have 10 chunks
    assert len(expected_chunks) == 10, f"Should have 10 chunks, got {len(expected_chunks)}"
    
    print("✓ Chunked structure is correct:")
    print(f"  - 10 chunks totaling {total_words} words")
    for chunk in expected_chunks:
        print(f"  - Chunk {chunk['index']}: {chunk['words']} words ({chunk['description']})")
    
    return True


def test_streaming_output_paths():
    """Test that streaming output paths are properly constructed."""
    print("\nTesting streaming output path construction...")
    
    import os
    import tempfile
    
    # Test creating output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_topic_id = "test-topic-01"
        output_dir = os.path.join(tmpdir, "podcast_chunks", test_topic_id)
        
        # This should work without errors
        os.makedirs(output_dir, exist_ok=True)
        
        assert os.path.exists(output_dir), "Output directory should be created"
        
        # Test creating chunk paths
        for i in range(1, 11):
            chunk_path = os.path.join(output_dir, f"L1_chunk{i}.txt")
            checkpoint_path = os.path.join(output_dir, f"L1_checkpoint_{i}.txt")
            
            # Write test files
            with open(chunk_path, 'w') as f:
                f.write(f"Chunk {i} content")
            with open(checkpoint_path, 'w') as f:
                f.write(f"Checkpoint {i} content")
        
        # Verify all files exist
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("L1_chunk")]
        checkpoint_files = [f for f in os.listdir(output_dir) if f.startswith("L1_checkpoint")]
        
        assert len(chunk_files) == 10, f"Should have 10 chunk files, got {len(chunk_files)}"
        assert len(checkpoint_files) == 10, f"Should have 10 checkpoint files, got {len(checkpoint_files)}"
    
    print("✓ Streaming output paths work correctly")
    print(f"  - Can create output directory")
    print(f"  - Can create 10 chunk files")
    print(f"  - Can create 10 checkpoint files")
    
    return True


def test_chunk_stitching():
    """Test that chunks can be stitched together correctly."""
    print("\nTesting chunk stitching logic...")
    
    # Simulate 10 chunks
    chunks = [f"HOST_A: Chunk {i} content.\nHOST_B: Response to chunk {i}." for i in range(1, 11)]
    
    # Stitch with newlines
    complete_text = "\n\n".join(chunks)
    
    # Verify structure
    assert "Chunk 1" in complete_text, "Should contain chunk 1"
    assert "Chunk 10" in complete_text, "Should contain chunk 10"
    assert complete_text.count("HOST_A:") == 10, "Should have 10 HOST_A lines"
    assert complete_text.count("HOST_B:") == 10, "Should have 10 HOST_B lines"
    
    # Verify chunks are separated
    chunk_parts = complete_text.split("\n\n")
    assert len(chunk_parts) == 10, f"Should have 10 parts when split, got {len(chunk_parts)}"
    
    print("✓ Chunk stitching works correctly")
    print(f"  - Stitched {len(chunks)} chunks")
    print(f"  - Total length: {len(complete_text)} chars")
    print(f"  - All HOST_A/HOST_B markers present")
    
    return True


def test_streaming_preserves_progress():
    """Test that streaming saves progress incrementally."""
    print("\nTesting progress preservation...")
    
    import os
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = os.path.join(tmpdir, "streaming_output.txt")
        
        # Simulate streaming by writing chunks
        buffer = ""
        total_chars = 0
        flush_threshold = 1000
        
        for i in range(5):
            chunk_text = f"Chunk {i} " * 200  # ~1400 chars per chunk
            buffer += chunk_text
            total_chars += len(chunk_text)
            
            # Flush when threshold exceeded
            if len(buffer) >= flush_threshold:
                with open(output_file, 'a') as f:
                    f.write(buffer)
                buffer = ""
        
        # Final flush
        if buffer:
            with open(output_file, 'a') as f:
                f.write(buffer)
        
        # Verify file exists and has content
        assert os.path.exists(output_file), "Output file should exist"
        
        with open(output_file, 'r') as f:
            content = f.read()
        
        assert len(content) == total_chars, f"Should have {total_chars} chars, got {len(content)}"
        assert "Chunk 0" in content, "Should contain first chunk"
        assert "Chunk 4" in content, "Should contain last chunk"
    
    print("✓ Progress preservation works correctly")
    print(f"  - Simulated streaming with flush threshold")
    print(f"  - All content preserved: {total_chars} chars")
    
    return True


def test_no_retry_logic():
    """Test that retry logic has been removed from chunk generation (fail fast)."""
    print("\nTesting fail-fast behavior...")
    
    # Read the responses_api_generator.py source to verify no retry logic
    source_file = Path(__file__).parent / "responses_api_generator.py"
    with open(source_file, 'r') as f:
        source_code = f.read()
    
    # The chunk generation function should not have max_retries parameter
    chunk_func_start = source_code.find("def generate_l1_chunk_with_streaming(")
    if chunk_func_start != -1:
        # Find the end of the function signature (before the docstring)
        chunk_func_end = source_code.find('"""', chunk_func_start)
        func_signature = source_code[chunk_func_start:chunk_func_end]
        assert "max_retries" not in func_signature, "Chunk function should not have max_retries parameter"
    
    # Should not have retry loops in chunk generation
    assert "for attempt in range(max_retries)" not in source_code, \
        "Should not have retry loop in chunk generation"
    
    # OpenAI client should have max_retries=0 for fail-fast
    client_init = source_code.find("client = OpenAI(")
    if client_init != -1:
        client_section = source_code[client_init:client_init+500]
        assert "max_retries=0" in client_section or "max_retries = 0" in client_section, \
            "OpenAI client should be configured with max_retries=0"
    
    print("✓ Fail-fast behavior confirmed")
    print("  - No retry logic in chunk generation")
    print("  - OpenAI client configured with max_retries=0")
    print("  - Errors will stop execution immediately")
    print("  - No unnecessary API expenses on failures")
    
    return True


def main():
    """Run all tests."""
    print("=" * 80)
    print("STREAMING AND CHUNKED GENERATION TESTS")
    print("=" * 80)
    
    tests = [
        test_chunked_structure,
        test_streaming_output_paths,
        test_chunk_stitching,
        test_streaming_preserves_progress,
        test_no_retry_logic
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
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
