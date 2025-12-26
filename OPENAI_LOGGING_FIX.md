# OpenAI API Logging and Error Handling Improvements

**Date**: 2025-12-17  
**Issue**: Response API error - 'Response' object has no attribute 'choices'  
**Status**: ✅ Fixed

---

## Problem Statement

The system was encountering errors when using OpenAI's Responses API (gpt-5.2-pro):

1. **Error Message**: `'Response' object has no attribute 'choices'`
2. **Small Chunk Size**: Responses were only 1022 characters when much longer responses were expected
3. **No Logging**: No visibility into what was sent to OpenAI and what was received back

### Root Cause Analysis

The error occurred because:
- The `extract_completion_text()` function assumed all responses had a `choices` attribute
- The `get_finish_reason()` function also assumed `choices[0].finish_reason` existed
- The Responses API has a different response structure than Chat Completions API
- No logging made it difficult to diagnose the actual issue

---

## Solution Implemented

### 1. Enhanced Response Extraction (`extract_completion_text()`)

**Changes Made**:
- Added comprehensive logging of response structure and attributes
- Implemented multiple extraction methods for Responses API:
  - Method 1: `response.output_text` (direct attribute)
  - Method 2: `response.output` (alternative structure)
  - Method 3: `response.choices[0].message.content` (chat-like format)
  - Method 4: `response.choices[0].text` (completion-like format)
- Added informative error messages showing what attributes are available
- Maintained backward compatibility with Chat and Completion endpoints

**Code Location**: `scripts/openai_utils.py`, lines 171-267

### 2. Robust Finish Reason Extraction (`get_finish_reason()`)

**Changes Made**:
- Added fallback logic to handle missing attributes gracefully
- Returns "unknown" instead of raising an exception when finish_reason is not found
- Checks multiple possible locations:
  - `response.choices[0].finish_reason` (standard)
  - `response.finish_reason` (top-level)
  - `response.status` (mapped to finish_reason equivalents)
- Added comprehensive logging

**Code Location**: `scripts/openai_utils.py`, lines 269-306

### 3. Comprehensive Request/Response Logging

**Added to `create_openai_completion()`**:
- Request parameters logging (model, max_tokens, temperature)
- Input/prompt preview (first 500 chars)
- Tools configuration
- Response type and attributes
- Token usage statistics (prompt, completion, total)
- Warning when approaching token limits (>95% of max_output_tokens)

**Added to `multi_format_generator.py`**:
- Generation start information (content specs count, max tokens)
- Per-chunk logging:
  - API call number
  - Raw response type and attributes
  - Extracted text length
  - Preview of first/last 200 characters
  - JSON structure validation (brace/bracket balance)
  - Continuation detection analysis
  - Finish reason
- Error context logging (last 3 messages sent)

**Code Locations**: 
- `scripts/openai_utils.py`, lines 59-61, 107-140, 168-178, 200-206, 228-234
- `scripts/multi_format_generator.py`, lines 296-375

### 4. Token Usage Monitoring

**Added Diagnostics**:
- Log token usage for all endpoints (Responses, Chat, Completion)
- Track prompt tokens vs completion tokens
- Warning when completion tokens approach max_output_tokens limit
- Helps diagnose why responses might be truncated

This addresses the "small chunk size" concern by providing visibility into:
- Whether the API is actually limiting output
- How many tokens are being used vs requested
- If we're hitting token limits

---

## Testing

### New Test Suite

Created `test_logging_improvements.py` with comprehensive tests:

**Test Coverage**:
1. **Response API Extraction** (5 test cases):
   - ✅ Extract from `output_text` attribute
   - ✅ Extract from `output` attribute
   - ✅ Extract from `choices[0].message.content`
   - ✅ Extract from `choices[0].text`
   - ✅ Proper error handling for invalid responses

2. **Finish Reason Robustness** (4 test cases):
   - ✅ Standard `choices[0].finish_reason`
   - ✅ Top-level `finish_reason`
   - ✅ Missing finish_reason (returns "unknown")
   - ✅ Status field mapping to finish_reason

3. **Backward Compatibility** (1 test case):
   - ✅ Chat Completions API still works correctly

**Test Results**: All 10 tests passing ✅

**Test Location**: `scripts/test_logging_improvements.py`

### Existing Tests

All existing tests continue to pass:
- ✅ `test_integration_endpoint_selection.py` (7 tests)
- ✅ `test_openai_endpoint_config.py` (19 tests)

---

## Usage

### Viewing Logs

The enhanced logging will automatically output detailed information when script generation runs:

```bash
# Set logging level to INFO (default)
python scripts/script_generate.py --topic topic-01

# The logs will show:
# - What is sent to OpenAI (request params, input preview)
# - What is received back (response type, attributes, token usage)
# - Extraction process (which method succeeded)
# - Any issues (truncation warnings, missing attributes)
```

### Understanding the Logs

**Request Logs**:
```
INFO: ================================================================================
INFO: OpenAI API Request - Model: gpt-5.2-pro, Endpoint: responses
INFO: ================================================================================
INFO: Using Responses API endpoint for model: gpt-5.2-pro
INFO: Request params: model=gpt-5.2-pro, max_output_tokens=32000
INFO: Input preview: You are creating multiple podcast scripts for: Technology & AI News...
```

**Response Logs**:
```
INFO: Response received from OpenAI Responses API
INFO: Response type: <class 'openai.types.responses.Response'>
INFO: Response attributes: ['output_text', 'usage', 'model_dump', ...]
INFO: Token usage: {'prompt_tokens': 1500, 'completion_tokens': 256, 'total_tokens': 1756}
INFO: Extracting text from responses endpoint response
INFO: Response has attributes: output_text, usage, model_dump, ...
INFO: Found output_text attribute, value type: <class 'str'>
INFO: Extracted 1022 chars from output_text
```

**Token Usage Analysis**:
```
INFO: Prompt tokens: 1500
INFO: Completion tokens: 256
INFO: Total tokens: 1756
WARNING: Response may be truncated: used 30400 of 32000 max_output_tokens
```

---

## Impact on Small Chunk Size Issue

The logging improvements help diagnose why response chunk size is small (1022 chars):

### What We Now See:

1. **Token Usage**: Logs show exactly how many completion tokens were used
2. **Truncation Detection**: Warning if we hit the token limit
3. **Response Structure**: Can see what attributes the response actually has
4. **Finish Reason**: Know if response stopped due to length limit or completion

### Possible Causes (Now Visible in Logs):

- **API Limit**: If completion_tokens ≈ max_output_tokens, we're hitting the limit
- **Model Behavior**: If finish_reason = "length", model stopped due to length
- **Response Format**: If response has different structure, we now see all attributes
- **Input Size**: If prompt_tokens is very high, less room for completion

### Next Steps for Investigation:

1. Check the logs for token usage during actual generation
2. If hitting limit: may need to adjust max_output_tokens or use streaming
3. If model stopping early: may need to adjust prompt or continuation logic
4. If response format different: logs now show exact structure to adapt to

---

## Files Modified

1. `scripts/openai_utils.py`
   - Enhanced `create_openai_completion()` with request/response logging
   - Fixed `extract_completion_text()` to handle all response formats
   - Fixed `get_finish_reason()` to handle missing attributes gracefully

2. `scripts/multi_format_generator.py`
   - Added detailed logging throughout generation loop
   - Log API call details, response info, continuation logic
   - Enhanced error context logging

3. `scripts/test_logging_improvements.py` (new)
   - Comprehensive test suite for new functionality
   - 10 test cases covering all scenarios

4. `OPENAI_LOGGING_FIX.md` (new)
   - This documentation file

---

## Benefits

✅ **Error Resolution**: Fixed 'Response' object has no attribute 'choices' error  
✅ **Diagnostic Capability**: Can now see what's sent and received from OpenAI  
✅ **Token Visibility**: Understand token usage and limits  
✅ **Robust Error Handling**: Graceful degradation when attributes missing  
✅ **Backward Compatible**: All existing tests still pass  
✅ **Future Proof**: Can adapt to API changes with visible structure  

---

## Related Files

- `scripts/openai_utils.py` - Core API interaction utilities
- `scripts/multi_format_generator.py` - Multi-format script generator
- `scripts/global_config.py` - Configuration (GPT_MODEL, MAX_COMPLETION_TOKENS)
- `RESPONSES_API_IMPLEMENTATION.md` - Responses API documentation
- `OPENAI_MODEL_CONFIGURATION.md` - Model endpoint configuration

---

**Status**: ✅ **Completed and Tested**  
**All Tests**: ✅ Passing (10/10 new tests + 26/26 existing tests)

---

**Last Updated**: 2025-12-17
