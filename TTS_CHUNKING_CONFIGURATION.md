# TTS Chunking Configuration

## Overview

The TTS (Text-to-Speech) system now supports configurable chunking strategies per topic, allowing you to choose between:
- **Single Run** (default): Process all dialogue in one continuous run per content type
- **Chunking Logic**: Split content into smaller chunks for parallel processing

## Configuration

### Global Default

The global default is set in `scripts/global_config.py`:

```python
TTS_USE_CHUNKING = False  # Default: Use single run per content type
```

### Per-Topic Configuration

Override the global default in your topic configuration file (`topics/topic-XX.json`):

```json
{
  "id": "topic-01",
  "title": "My Topic",
  "tts_use_chunking": false
}
```

Note: Set to `true` to enable chunking, `false` for single run.

**Configuration precedence:**
1. Topic-specific `tts_use_chunking` field (if present)
2. Global `TTS_USE_CHUNKING` setting (fallback)

## Strategies Comparison

### Single Run (Default - `tts_use_chunking: false`)

**When to use:**
- Most content types (short, medium, reels)
- Simpler, more reliable processing
- Lower overhead
- Default behavior for backward compatibility

**Characteristics:**
- Processes all dialogue in one continuous run
- Simpler error handling
- Lower memory overhead
- Suitable for most content types

**Example output:**
```
Using single run strategy (13000 chars)
```

### Chunking Logic (`tts_use_chunking: true`)

**When to use:**
- Very long-form content (60+ minute podcasts)
- Large content where parallel processing improves performance
- When you need parallel processing for better throughput
- When you need better resilience and retry logic for large files

**Characteristics:**
- Splits text into optimized chunks
- Parallel synthesis with retry logic
- Deterministic stitching with configurable gaps
- Comprehensive telemetry and logging
- Resume capability for failed chunks

**Example output:**
```
Using chunking strategy (130000 chars)
```

## Configuration Examples

### Example 1: Short Content (Default)

```json
{
  "id": "topic-news",
  "title": "Daily News Brief",
  "content_types": {
    "short": true,
    "reels": true
  }
}
```

Note: No `tts_use_chunking` specified - uses global default (false).

### Example 2: Long-Form Content with Chunking

```json
{
  "id": "topic-longform",
  "title": "Deep Dive Analysis",
  "content_types": {
    "long": true
  },
  "tts_use_chunking": true
}
```

Note: Chunking enabled for 60-minute podcasts.

### Example 3: Mixed Configuration

```json
{
  "id": "topic-mixed",
  "title": "Mixed Format Topic",
  "content_types": {
    "long": true,
    "medium": true,
    "short": true
  },
  "tts_use_chunking": false
}
```

Note: Single run used even for long content.

## Technical Details

### Single Run Implementation

Function: `_tts_traditional()` in `scripts/tts_generate.py`

- Processes dialogue chunks sequentially
- Concatenates audio with gaps
- Converts to final MP3 format

### Chunking Implementation

Function: `_tts_with_chunking()` in `scripts/tts_generate.py`

Delegates to `generate_tts_with_chunking()` in `scripts/tts_chunker.py`:

1. **Smart Chunking**: Respects sentence boundaries, speaker changes
2. **Parallel Synthesis**: Configurable concurrency (default: 4 workers)
3. **Retry Logic**: Automatic retries on failure (default: 3 attempts)
4. **Deterministic Stitching**: FFmpeg-based audio concatenation
5. **Telemetry**: Comprehensive logging and metrics

### Chunking Parameters

Configured in `scripts/global_config.py`:

```python
TTS_MAX_CHARS_PER_CHUNK = 5000      # Max characters per chunk
TTS_MAX_SENTENCES_PER_CHUNK = 50    # Max sentences per chunk
TTS_GAP_MS = 500                     # Gap between chunks (ms)
TTS_CONCURRENCY = 4                  # Parallel workers
TTS_RETRY_ATTEMPTS = 3               # Retry attempts per chunk
```

## Validation

The configuration is validated during topic config validation:

```python
from global_config import validate_topic_config

config = {
    'id': 'test',
    'title': 'Test',
    'queries': ['test'],
    'tts_use_chunking': True  # Must be boolean
}

result = validate_topic_config(config)
# result['status'] will be 'error' if tts_use_chunking is not boolean
```

## Testing

### Unit Tests

```bash
cd scripts
python test_tts_chunking_config.py
```

Tests:
- Global default configuration
- Topic config validation
- Boolean type checking
- Optional field handling

### Integration Tests

```bash
cd scripts
python test_tts_chunking_integration.py
```

Tests:
- TTS logic routing based on config
- Config precedence (topic vs global)
- Single run vs chunking selection
- Large content handling

## Migration Guide

### For Existing Topics

**No changes required!** 

All existing topics will use the single run approach (global default is `false`), maintaining backward compatibility.

### To Enable Chunking

Add to your topic configuration:

```json
{
  "tts_use_chunking": true
}
```

### To Explicitly Disable Chunking

Add to your topic configuration:

```json
{
  "tts_use_chunking": false
}
```

## Troubleshooting

### Chunking Not Working

Check:
1. `tts_use_chunking` is set to `true` in topic config
2. `tts_chunker` module is available (check import in `tts_generate.py`)
3. Piper TTS binaries are properly installed

### Performance Issues

If single run is too slow for large content:
1. Enable chunking: `"tts_use_chunking": true`
2. Adjust concurrency: Modify `TTS_CONCURRENCY` in `global_config.py`

### Audio Quality Issues

If chunking produces gaps or artifacts:
1. Adjust `TTS_GAP_MS` in `global_config.py`
2. Consider using single run: `"tts_use_chunking": false`

## Related Documentation

- `scripts/global_config.py` - Configuration constants
- `scripts/tts_generate.py` - TTS generation logic
- `scripts/tts_chunker.py` - Chunking implementation
- `TTS_TROUBLESHOOTING_GUIDE.md` - General TTS troubleshooting
- `TTS_WORKFLOW_IMPROVEMENTS_SUMMARY.md` - TTS workflow improvements

## Summary

The TTS chunking configuration provides flexible control over audio generation strategy:

- ✅ **Default**: Single run (simple, reliable)
- ✅ **Optional**: Chunking logic (parallel, resilient)
- ✅ **Per-topic**: Override global default
- ✅ **Validated**: Type checking and error reporting
- ✅ **Backward compatible**: No changes needed for existing topics
- ✅ **Tested**: Comprehensive unit and integration tests

Choose the strategy that best fits your content type and performance requirements!
