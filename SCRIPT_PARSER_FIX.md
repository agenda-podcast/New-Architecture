# Script Parser Fix - 0 Dialogue Chunks Issue

## Problem Summary
Generated script files had 0 dialogue chunks, causing TTS generation to fail with error:
```
R1.script: topic-01-20251218-R1.script.json processed during TTS generation had 0 dialogue chunks
```

## Root Cause Analysis

### Architecture Gap
The podcast generation system has a two-pass architecture:
- **Pass A** (gpt-5.2-pro): Generates L1 + canonical_pack + sources
- **Pass B** (gpt-4.1-nano): Generates M1-M2, S1-S4, R1-R8

Both passes return content with a **"script"** field containing dialogue in text format:
```
HOST_A: Welcome to the show!
HOST_B: Thanks for having me!
```

However, the downstream processing in `script_generate.py` expected content with a **"segments"** field containing structured dialogue arrays:
```json
{
  "segments": [
    {
      "chapter": 1,
      "dialogue": [
        {"speaker": "A", "text": "Welcome to the show!"},
        {"speaker": "B", "text": "Thanks for having me!"}
      ]
    }
  ]
}
```

### The Missing Link
There was no parser to convert between these two formats. As a result:
1. `content_item.get('segments', [])` returned `[]`
2. Script files were saved with empty segments
3. TTS generation found 0 dialogue chunks
4. Workflow failed

## Solution Implementation

### 1. Created Script Parser Module (`scripts/script_parser.py`)

**Core Functions:**
- `parse_script_text_to_segments()` - Converts HOST_A/HOST_B text to segments
- `parse_script_text_to_multi_segments()` - Splits long scripts into multiple segments
- `convert_content_script_to_segments()` - Wrapper for content items
- `validate_segments()` - Validates segment structure and dialogue

**Key Features:**
- Regex-based parsing of HOST_A/HOST_B markers
- Automatic segment creation with dialogue arrays
- Multi-segment support for long-form content
- Comprehensive validation
- Detailed logging for debugging

### 2. Integrated Parser into Script Generation

**Modified `scripts/script_generate.py`:**
```python
# Convert script text to segments if needed
if convert_content_script_to_segments is not None:
    content_item = convert_content_script_to_segments(content_item)

segments = content_item.get('segments', [])

# Validate segments before proceeding
if not segments:
    print(f"ERROR: {code} has no segments!")
    continue

if validate_segments(segments, code):
    total_dialogue = sum(len(seg.get('dialogue', [])) for seg in segments)
    print(f"  {code}: {len(segments)} segment(s), {total_dialogue} dialogue items")
```

### 3. Fixed TESTING_MODE Handling

**Modified `scripts/responses_api_generator.py`:**
- API key check now respects TESTING_MODE
- Allows testing without real API credentials
- Uses mock responses when TESTING_MODE=True

### 4. Added Comprehensive Testing

**Created `scripts/test_script_parser.py`:**
- 7 test cases covering all parsing scenarios
- Tests with real mock data
- All tests passing ✓

## Test Results

### Parser Tests
```
Test 1: Basic script parsing ✓
Test 2: Empty script handling ✓
Test 3: Script with no HOST markers ✓
Test 4: Multi-segment parsing ✓
Test 5: Content item conversion ✓
Test 6: Segment validation ✓
Test 7: Real mock data parsing ✓

Results: 7/7 tests passed
```

### Script Generation Test
```
Generated 15 content pieces:
- L1: 3 segments, 273 dialogue items ✓
- M1: 1 segment, 85 dialogue items ✓
- M2: 1 segment, 161 dialogue items ✓
- S1: 1 segment, 89 dialogue items ✓
- S2: 1 segment, 82 dialogue items ✓
- S3: 1 segment, 74 dialogue items ✓
- S4: 1 segment, 78 dialogue items ✓
- R1: 1 segment, 9 dialogue items ✓
- R2: 1 segment, 9 dialogue items ✓
- R3: 1 segment, 9 dialogue items ✓
- R4: 1 segment, 10 dialogue items ✓
- R5: 1 segment, 10 dialogue items ✓
- R6: 1 segment, 10 dialogue items ✓
- R7: 1 segment, 10 dialogue items ✓
- R8: 1 segment, 9 dialogue items ✓
```

### Example Output (R1.script.json)
```json
{
  "title": "Donald J Trump - R1",
  "duration_sec": 0,
  "segments": [
    {
      "chapter": 1,
      "title": "Reels",
      "start_time": 0,
      "duration": 0,
      "dialogue": [
        {"speaker": "A", "text": "Breaking: New AI regulations just dropped!"},
        {"speaker": "B", "text": "All large AI models need safety audits..."},
        ...
      ]
    }
  ]
}
```

## Impact & Prevention

### Immediate Impact
- ✓ Scripts now have dialogue chunks
- ✓ TTS generation will work correctly
- ✓ Workflow will complete successfully

### Prevention Measures
1. **Automatic Conversion**: Parser runs automatically for all content
2. **Validation**: Scripts with 0 dialogue are rejected before saving
3. **Logging**: Detailed logs show segment and dialogue counts
4. **Error Messages**: Clear explanations when issues occur
5. **Testing**: Comprehensive test suite prevents regressions

### Logging Output
The fix adds detailed logging at each step:
```
INFO:script_parser:Converting script text to segments for R1 (reels)
INFO:script_parser:Parsed 9 dialogue items from script text
INFO:script_parser:  R1: Created 1 segment(s) with 9 dialogue items
INFO:script_parser:R1: Validation passed - 1 segments with 9 dialogue items
```

## Files Changed

### New Files
- `scripts/script_parser.py` - Parser implementation (260 lines)
- `scripts/test_script_parser.py` - Test suite (217 lines)
- `SCRIPT_PARSER_FIX.md` - This documentation

### Modified Files
- `scripts/script_generate.py` - Integrated parser (30 lines changed)
- `scripts/responses_api_generator.py` - Fixed TESTING_MODE (15 lines changed)

## Security Review
- ✓ No security vulnerabilities found (CodeQL)
- ✓ No code review issues (minor nitpicks addressed)
- ✓ Input validation implemented
- ✓ Error handling comprehensive

## Next Steps

### For Production Use
1. Set `TESTING_MODE = False` in `scripts/global_config.py`
2. Ensure `GPT_KEY` or `OPENAI_API_KEY` environment variable is set
3. Run pipeline: `python scripts/run_pipeline.py --topic topic-01`
4. Verify TTS generation completes successfully

### For Development/Testing
1. Keep `TESTING_MODE = True` (current setting)
2. Mock responses will be used (no API key needed)
3. Run tests: `python scripts/test_script_parser.py`
4. All tests should pass

## Monitoring

### Success Indicators
Look for these in logs:
```
✓ Successfully generated all 15 scripts
L1: 3 segment(s), 273 dialogue items
...
TTS Generation Summary:
  Success: 15/15
```

### Failure Indicators
If you see any of these, investigate:
```
ERROR: {code} has no segments!
ERROR: {code} has invalid segments!
No dialogue items found across all segments!
```

## Conclusion

This fix resolves the 0 dialogue chunks issue by:
1. Adding the missing script-to-segments parser
2. Integrating it seamlessly into the workflow
3. Validating all outputs
4. Providing comprehensive logging
5. Including thorough testing

The implementation is minimal, targeted, and includes proper error handling to prevent similar issues in the future.
