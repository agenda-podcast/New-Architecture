# Streaming Implementation Guide

**Date**: 2025-12-18  
**Feature**: Streaming and Chunked Generation for Pass A (L1)  
**Status**: ✅ Implementation Complete

---

## Overview

This document describes the implementation of **streaming and chunked generation** for Pass A in the two-pass architecture. This solves the critical timeout/disconnection problem that occurred when generating 10,000-word L1 content in a single API call.

### Problem Statement

The original Pass A implementation had the following issues:
1. **Long wait times**: 10,000-word generation took 15-30 minutes
2. **Server disconnections**: OpenAI servers would disconnect before completion
3. **No partial progress**: If disconnected, all progress was lost
4. **High failure rate**: Long idle periods made production unreliable

### Solution

**Chunked Generation with Streaming**:
- Split L1 (10,000 words) into **10 chunks** of ~1,000 words each
- Use **streaming API** for each chunk to receive tokens as they're generated
- Write partial output to disk as it arrives (every 20,000 chars)
- Save checkpoints after each chunk completes
- **Fail fast** with no retries (to avoid API expenses)
- Stitch final L1 from completed chunks

---

## Architecture Changes

### New Functions in `openai_utils.py`

#### `create_openai_streaming_completion()`

New streaming wrapper that:
- Enables `stream=True` on Responses API
- Iterates over streaming events (`response.output_text.delta`)
- Writes to disk incrementally with configurable flush threshold
- Returns complete accumulated text
- Logs progress every 10,000 chars

**Key Parameters**:
- `output_path`: File path to write streaming output
- `flush_threshold`: Buffer size before flushing (default: 20,000 chars)

**Example Usage**:
```python
response_text = create_openai_streaming_completion(
    client=client,
    model="gpt-5.2-pro",
    messages=[...],
    tools=[{"type": "web_search"}],
    max_completion_tokens=2000,
    output_path="/tmp/output.txt",
    flush_threshold=20000
)
```

### New Functions in `responses_api_generator.py`

#### `generate_l1_chunk_with_streaming()`

Generates a single L1 chunk with streaming:
- Chunk 1: Calls web_search, generates sources + canonical_pack + chunk text
- Chunks 2-10: Use canonical_pack from chunk 1, generate only chunk text
- Streams output to `output_path.chunk{N}`
- **No retry logic** - fails immediately on error to avoid API expenses

#### `generate_l1_in_chunks()`

Orchestrates the 10-chunk generation:
- Creates output directory: `/tmp/podcast_chunks/{topic_id}/`
- Generates 10 chunks sequentially
- Saves checkpoint after each chunk: `L1_checkpoint_{N}.txt`
- Stitches all chunks together with `\n\n` separator
- Saves final L1: `L1_complete.txt`

#### Updated `generate_pass_a_content()`

Now uses chunked generation instead of single API call:
- Calls `generate_l1_in_chunks()` instead of `create_openai_completion()`
- Returns stitched L1 content with sources and canonical_pack
- Preserves same interface for Pass B compatibility

---

## Chunk Structure

L1 is split into 10 chunks aligned with content segments:

| Chunk | Words | Description |
|-------|-------|-------------|
| 1 | 400 | Cold Open - Hook the audience |
| 2 | 1600 | What Happened - Timeline of events |
| 3 | 1400 | Why It Matters - Context and significance |
| 4 | 1500 | Deep Dive Part 1 - Technical details |
| 5 | 1500 | Deep Dive Part 2 - Market implications |
| 6 | 1500 | Deep Dive Part 3 - Broader context |
| 7 | 700 | Rumor Watch - Unconfirmed reports |
| 8 | 600 | What's Next - Future predictions |
| 9 | 500 | Actionable Insights - What to know/do |
| 10 | 300 | Wrap + CTA - Summary and call to action |

**Total**: 10,000 words

---

## Streaming Flow

### Chunk 1 Generation

```
1. Build prompt with topic, description, hosts, freshness window
2. Include web_search tool
3. Request: sources + canonical_pack + chunk_text
4. Stream response to: {temp_dir}/podcast_chunks/{topic_id}/L1_chunk1.txt.chunk1
5. Parse JSON: extract sources, canonical_pack, chunk_text
6. Save checkpoint: L1_checkpoint_1.txt
```

### Chunks 2-10 Generation

```
1. Build prompt with canonical_pack from chunk 1
2. NO web_search (use existing facts only)
3. Request: chunk_text only
4. Stream response to: {temp_dir}/podcast_chunks/{topic_id}/L1_chunk{N}.txt.chunk{N}
5. Parse JSON: extract chunk_text
6. Append to accumulated chunks
7. Save checkpoint: L1_checkpoint_{N}.txt
```

### Final Stitching

```
1. Join all 10 chunks with "\n\n"
2. Save final L1: L1_complete.txt
3. Build l1_content structure with script and metadata
4. Return (sources, canonical_pack, l1_content)
```

---

## Fail-Fast Design

### No Retry Logic

**Rationale**: User pays per API request. Retrying on errors wastes money on potentially broken logic.

**Implementation**:
- OpenAI client configured with `max_retries=0`
- No retry loops in chunk generation functions
- SDK will not automatically retry failed requests

**Behavior**:
- If any chunk fails, **stop immediately**
- Log the error clearly
- Do not retry automatically
- User must analyze the issue before re-running

**What's Preserved**:
- All completed chunks are saved to disk
- Checkpoints show progress up to failure point
- Streaming output files contain partial responses
- User can diagnose issues without losing all work

### Error Handling

```python
# NO RETRY LOOP - FAIL FAST
try:
    response_text = create_openai_streaming_completion(...)
    chunk_data = json.loads(response_text)
    return chunk_data['chunk_text']
except Exception as e:
    logger.error(f"Error generating chunk {chunk_index}: {e}")
    raise  # Stop immediately, don't retry
```

---

## Benefits

### Reliability

✅ **Survives disconnects**: Each chunk is ~1,000 words (2-3 minutes), reducing timeout risk  
✅ **Preserves progress**: Checkpoints after each chunk prevent total loss  
✅ **Streaming output**: Partial text written to disk as it arrives  
✅ **Fail fast**: Errors stop execution immediately to prevent API waste

### Observability

✅ **Real-time progress**: Logs show chars received every 10k chars  
✅ **Checkpoint files**: Can see exactly how far generation progressed  
✅ **Per-chunk files**: Each chunk's output preserved separately  
✅ **Clear errors**: Immediate failure with context for debugging

### Cost Control

✅ **No retries**: Failed chunks don't incur multiple API charges  
✅ **Web search once**: Only chunk 1 uses expensive web_search tool  
✅ **Incremental**: Can resume from last successful chunk (future enhancement)  

---

## File Outputs

For topic `topic-01`, chunked generation creates files in the system temp directory:

```
{temp_dir}/podcast_chunks/topic-01/
├── L1_chunk1.txt.chunk1        # Raw streaming output for chunk 1
├── L1_chunk2.txt.chunk2        # Raw streaming output for chunk 2
├── ...
├── L1_chunk10.txt.chunk10      # Raw streaming output for chunk 10
├── L1_checkpoint_1.txt         # Checkpoint after chunk 1
├── L1_checkpoint_2.txt         # Checkpoint after chunks 1-2
├── ...
├── L1_checkpoint_10.txt        # Checkpoint after all chunks
└── L1_complete.txt             # Final stitched L1 (10,000 words)
```

**Note**: `{temp_dir}` is determined by `tempfile.gettempdir()`:
- Linux/Mac: `/tmp/`
- Windows: `C:\Users\{username}\AppData\Local\Temp\`

**Checkpoint files** contain cumulative content:
- `L1_checkpoint_1.txt`: Just chunk 1
- `L1_checkpoint_2.txt`: Chunks 1-2 stitched
- `L1_checkpoint_10.txt`: All 10 chunks (same as `L1_complete.txt`)

---

## Testing

### Unit Tests: `test_streaming_generation.py`

Tests verify:
1. ✅ Chunk structure (10 chunks totaling 10,000 words)
2. ✅ Output path creation and file writing
3. ✅ Chunk stitching logic
4. ✅ Progress preservation with streaming
5. ✅ No retry logic (fail-fast confirmed)

**Run tests**:
```bash
python scripts/test_streaming_generation.py
```

### Integration Testing

To test with real API (requires OpenAI credentials):
```bash
python scripts/script_generate.py --topic topic-01
```

Expected behavior:
- Logs show "PASS A: Generating L1 + canonical_pack with STREAMING in 10 chunks"
- Progress logged for each chunk (1/10, 2/10, ...)
- Checkpoint files created in `/tmp/podcast_chunks/`
- Final L1 stitched and passed to Pass B

---

## Configuration

No new configuration needed. Streaming is automatically used in Pass A.

### Environment Variables

Same as before:
- `GPT_KEY` or `OPENAI_API_KEY`: Required for API access

### Model Requirements

- **gpt-5.2-pro**: Must support streaming in Responses API
- Verify model has streaming capability before use

---

## Monitoring

### Key Metrics

**Per-chunk**:
- Generation time (should be 2-5 minutes per chunk)
- Characters received
- Actual word count vs target

**Overall**:
- Total time (should be 20-50 minutes for all 10 chunks)
- Success rate (chunks completed / chunks attempted)
- Checkpoint preservation

### Log Output

```
INFO: PASS A: Generating L1 + canonical_pack with STREAMING in 10 chunks
INFO: Generating L1 chunk 1/10
INFO: Target: 400 words, covering: Cold Open - Hook the audience
INFO: Starting to receive streaming response...
INFO: Received 10000 chars so far...
INFO: Flushed 20000 chars to {temp_dir}/podcast_chunks/topic-01/L1_chunk1.txt.chunk1
INFO: Streaming complete: 2500 total chars received
INFO: Chunk 1 received: 2500 chars
INFO: Chunk 1: Retrieved 12 sources and canonical_pack
INFO: Checkpoint saved: {temp_dir}/podcast_chunks/topic-01/L1_checkpoint_1.txt
INFO: Generating L1 chunk 2/10
...
INFO: Final L1 saved: {temp_dir}/podcast_chunks/topic-01/L1_complete.txt (65000 chars)
INFO: CHUNKED GENERATION COMPLETE: 10 chunks stitched
```

---

## Migration Notes

### Backward Compatibility

✅ **Interface unchanged**: `generate_pass_a_content()` returns same structure  
✅ **Pass B unaffected**: Still receives sources, canonical_pack, l1_content  
✅ **TTS/video pipeline**: Works with stitched L1 exactly as before  

### Rollout

**Automatic**: All Pass A generation now uses streaming and chunking.

**Rollback**: If issues arise, can revert to single API call by:
1. Commenting out `generate_l1_in_chunks()` call
2. Uncommenting original `create_openai_completion()` logic

---

## Future Enhancements

### Resume from Checkpoint

Add ability to resume from last successful chunk:
```python
# Check for existing checkpoints
last_checkpoint = find_last_checkpoint(output_dir)
if last_checkpoint:
    start_from_chunk = last_checkpoint + 1
else:
    start_from_chunk = 1
```

### Parallel Chunk Generation

Generate multiple chunks in parallel (chunks 2-10 can run concurrently):
```python
import asyncio

async def generate_all_chunks():
    # Chunk 1 first (for canonical_pack)
    await generate_chunk_1()
    
    # Chunks 2-10 in parallel
    tasks = [generate_chunk_n(i) for i in range(2, 11)]
    await asyncio.gather(*tasks)
```

### Adaptive Chunking

Adjust chunk sizes based on topic complexity:
```python
if config.get('topic_complexity') == 'high':
    # More, smaller chunks for complex topics
    chunks = 15  # 666 words each
else:
    # Standard chunking
    chunks = 10  # 1000 words each
```

---

## Troubleshooting

### Chunk Generation Fails

**Symptom**: Error during chunk N generation, process stops

**Check**:
1. Review error message in logs
2. Check partial output in `{temp_dir}/podcast_chunks/{topic_id}/L1_chunk{N}.txt.chunk{N}`
3. Verify API key and model access
4. Check OpenAI status: https://status.openai.com/

**Recovery**:
- Fix underlying issue
- Re-run generation (future: will support resume from checkpoint)

### Streaming Timeout

**Symptom**: Chunk generation hangs, no progress logged

**Possible causes**:
- Network connectivity issues
- OpenAI server overload
- Chunk prompt too complex

**Solutions**:
- Check network connection
- Reduce chunk word count
- Simplify chunk prompt

### JSON Parse Error

**Symptom**: `json.JSONDecodeError` after chunk generation

**Check**:
1. View raw output in chunk file
2. Verify JSON structure in response
3. Check for incomplete response (truncation)

**Solutions**:
- Increase `max_output_tokens` for chunk
- Simplify chunk prompt to reduce output size
- Check model's JSON formatting consistency

---

## Related Files

- `scripts/openai_utils.py` - Streaming API wrapper
- `scripts/responses_api_generator.py` - Chunked generation logic
- `scripts/test_streaming_generation.py` - Streaming tests
- `RESPONSES_API_IMPLEMENTATION.md` - Two-pass architecture doc

---

**Status**: ✅ **Production Ready**  
**Last Updated**: 2025-12-18
