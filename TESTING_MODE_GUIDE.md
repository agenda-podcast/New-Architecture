# Testing Mode Guide

**Date**: 2025-12-18  
**Feature**: Mock Responses for Testing Without API Calls  
**Status**: ✅ Complete and Tested

---

## Overview

Testing mode allows you to run the podcast generation pipeline without making real OpenAI API calls. This is useful for:
- **Development and debugging** without API costs
- **Testing pipeline changes** without waiting for slow API responses
- **CI/CD integration** where real API keys might not be available
- **Learning the codebase** without spending money

---

## Quick Start

### Enable Testing Mode

Edit `scripts/global_config.py` and set:

```python
TESTING_MODE = True
```

That's it! Now all API calls will use saved mock responses instead of calling OpenAI.

### Disable Testing Mode

Set it back to False for production use:

```python
TESTING_MODE = False
```

---

## How It Works

### Architecture

When `TESTING_MODE = True`:
1. **Pass A** loads mock response from `test_data/mock_responses/pass_a_response.json`
2. **Pass B** loads mock response from `test_data/mock_responses/pass_b_response.json`
3. No OpenAI API calls are made
4. Processing continues with the mock data

When `TESTING_MODE = False`:
1. **Pass A** generates real content with streaming API calls
2. **Pass B** generates real content with standard API calls
3. Both responses are **automatically saved** to mock response files for future testing
4. Normal processing continues

### Automatic Mock Response Generation

The system automatically captures real API responses for testing:

```python
# When TESTING_MODE = False, responses are saved automatically
sources, canonical_pack, l1_content = generate_pass_a_content(config, api_key, client)
# → Saves to test_data/mock_responses/pass_a_response.json

content_list = generate_pass_b_content(canonical_pack, config, api_key, client)
# → Saves to test_data/mock_responses/pass_b_response.json
```

This means:
- **First run**: Use real API, responses are saved
- **Subsequent runs**: Enable testing mode to reuse saved responses

---

## Mock Response Structure

### Pass A Response (`pass_a_response.json`)

```json
{
  "sources": [
    {
      "title": "Article Title",
      "publisher": "Publisher Name",
      "date": "2025-12-17",
      "url": "https://example.com/article"
    }
  ],
  "canonical_pack": {
    "timeline": "Chronological events...",
    "key_facts": "Core facts...",
    "key_players": "People and organizations...",
    "claims_evidence": "Claims and supporting evidence...",
    "beats_outline": "Story structure...",
    "punchlines": "Memorable quotes...",
    "historical_context": "Background and precedents..."
  },
  "l1_content": {
    "code": "L1",
    "type": "long",
    "target_words": 10000,
    "script": "HOST_A: dialogue text...\nHOST_B: dialogue text...",
    "actual_words": 850
  }
}
```

### Pass B Response (`pass_b_response.json`)

```json
{
  "content": [
    {
      "code": "M1",
      "type": "medium",
      "target_words": 2500,
      "script": "HOST_A: dialogue...\nHOST_B: dialogue...",
      "actual_words": 420
    },
    {
      "code": "M2",
      "type": "medium",
      "target_words": 2500,
      "script": "HOST_A: dialogue...\nHOST_B: dialogue...",
      "actual_words": 380
    },
    // ... S1-S4 (4 short formats)
    // ... R1-R8 (8 reel formats)
  ]
}
```

**Total**: 14 content pieces (M1-M2, S1-S4, R1-R8)

---

## Usage Examples

### Development Workflow

```bash
# 1. First, generate real content to capture responses
# Edit global_config.py: TESTING_MODE = False
python scripts/script_generate.py --topic topic-01

# 2. Enable testing mode for fast iteration
# Edit global_config.py: TESTING_MODE = True
python scripts/script_generate.py --topic topic-01

# 3. Now runs in seconds instead of minutes!
```

### Testing New Features

```python
# Test script
import global_config
global_config.TESTING_MODE = True

# Your test code here - uses mock responses
from responses_api_generator import generate_pass_a_content

config = {...}
sources, canonical_pack, l1_content = generate_pass_a_content(config, "fake_key", None)
# Uses mock data, no API call
```

### CI/CD Pipeline

```yaml
# GitHub Actions example
- name: Run tests with mock responses
  env:
    TESTING_MODE: "True"
  run: |
    python scripts/test_mock_responses.py
    python scripts/test_two_pass_generation.py
```

---

## Testing

Run the mock response tests:

```bash
python scripts/test_mock_responses.py
```

Expected output:
```
================================================================================
MOCK RESPONSE TESTING MODE TESTS
================================================================================
Testing mock response path construction...
✓ Pass A path: .../test_data/mock_responses/pass_a_response.json
✓ Pass B path: .../test_data/mock_responses/pass_b_response.json

Testing loading of existing mock responses...
✓ Pass A mock loaded: 2 sources, 850 words
✓ Pass B mock loaded: 14 content pieces
  Codes: M1, M2, S1, S2, S3, S4, R1, R2, R3, R4, R5, R6, R7, R8

Testing save/load roundtrip...
✓ Save/load roundtrip successful

Testing TESTING_MODE flag...
✓ TESTING_MODE flag accessible and working

================================================================================
RESULTS: 4 passed, 0 failed
================================================================================
```

---

## Configuration

### Global Config Settings

**`scripts/global_config.py`**:

```python
# Testing Configuration
TESTING_MODE = False  # Set to True to use mock responses
MOCK_RESPONSES_DIR = "test_data/mock_responses"  # Directory for saved responses
```

### Customizing Mock Responses

You can edit the mock response files directly:

1. **Modify content**: Edit `test_data/mock_responses/pass_a_response.json` or `pass_b_response.json`
2. **Change word counts**: Update `actual_words` fields
3. **Add/remove sources**: Modify the `sources` array
4. **Customize dialogue**: Edit the `script` fields

---

## Benefits

### Development Speed
✅ **Instant iteration**: No waiting for 20-50 minute API calls  
✅ **Fast debugging**: Reproduce issues without API delays  
✅ **Quick testing**: Run tests in seconds instead of minutes  

### Cost Savings
✅ **Zero API costs**: No charges during development/testing  
✅ **Predictable expenses**: Only pay for production runs  
✅ **Safe experimentation**: Try changes without financial risk  

### Reliability
✅ **Consistent results**: Same mock data every time  
✅ **No rate limits**: Test as many times as needed  
✅ **Offline development**: Work without internet/API access  

---

## Limitations

### What Testing Mode Does NOT Test

⚠️ **API connectivity**: Mock mode skips actual API calls  
⚠️ **New model behavior**: Uses saved responses, not live model output  
⚠️ **Streaming functionality**: Mock mode returns complete responses  
⚠️ **Rate limiting**: No rate limit testing in mock mode  

### When to Use Real API

Use `TESTING_MODE = False` when:
- Testing with new topics/content
- Validating model prompt changes
- Checking streaming behavior
- Capturing fresh responses for mocks
- Production content generation

---

## Troubleshooting

### Mock Response File Not Found

**Error**: `FileNotFoundError: Mock response file not found`

**Solution**: Run with `TESTING_MODE = False` first to generate and save responses:

```python
# In global_config.py
TESTING_MODE = False  # Generate real responses first
```

Then set `TESTING_MODE = True` for subsequent runs.

### Mock Response Out of Date

If mock responses are old or don't match your current needs:

1. Set `TESTING_MODE = False`
2. Run script generation once
3. New responses are automatically saved
4. Set `TESTING_MODE = True` again

### Custom Mock Responses

To create custom mock responses:

1. Copy existing mock file as template
2. Edit JSON structure to match your needs
3. Save to `test_data/mock_responses/`
4. Enable testing mode and run

---

## API Reference

### Configuration

```python
from global_config import TESTING_MODE, MOCK_RESPONSES_DIR
```

- `TESTING_MODE` (bool): Enable/disable mock responses
- `MOCK_RESPONSES_DIR` (str): Directory path for mock files

### Functions

```python
from responses_api_generator import (
    get_mock_response_path,
    save_mock_response,
    load_mock_response
)
```

**`get_mock_response_path(pass_name: str) -> str`**
- Get file path for a mock response
- Args: `"pass_a"` or `"pass_b"`
- Returns: Full path to mock file

**`save_mock_response(pass_name: str, response_data: dict) -> None`**
- Save response data to mock file
- Automatically called when `TESTING_MODE = False`
- Creates directory if needed

**`load_mock_response(pass_name: str) -> dict`**
- Load mock response from file
- Automatically called when `TESTING_MODE = True`
- Raises `FileNotFoundError` if file missing

---

## Files

### Source Files
- `scripts/global_config.py` - Configuration with TESTING_MODE flag
- `scripts/responses_api_generator.py` - Mock response handling logic
- `scripts/test_mock_responses.py` - Test suite for mock functionality

### Data Files
- `test_data/mock_responses/pass_a_response.json` - Pass A mock data
- `test_data/mock_responses/pass_b_response.json` - Pass B mock data

### Documentation
- `TESTING_MODE_GUIDE.md` - This document

---

## Best Practices

### During Development
1. ✅ Use `TESTING_MODE = True` for fast iteration
2. ✅ Periodically refresh mocks with real API calls
3. ✅ Test major changes with real API before deploying

### Before Deployment
1. ✅ Set `TESTING_MODE = False` in production config
2. ✅ Verify real API calls work end-to-end
3. ✅ Document any mock response customizations

### For Testing
1. ✅ Keep mock responses in version control
2. ✅ Update mocks when API responses change
3. ✅ Use consistent mock data across team

---

## Migration from Previous Version

If you were using the codebase before testing mode:

**No changes required!** The default is `TESTING_MODE = False`, so existing behavior is unchanged.

To adopt testing mode:
1. Run your pipeline once normally (generates mocks automatically)
2. Set `TESTING_MODE = True` in `global_config.py`
3. Future runs use saved responses

---

## Summary

- **Enable**: Set `TESTING_MODE = True` in `global_config.py`
- **Generate mocks**: Run once with `TESTING_MODE = False`
- **Use mocks**: Run with `TESTING_MODE = True` for instant results
- **Test**: `python scripts/test_mock_responses.py`
- **Benefits**: Fast iteration, zero API costs, offline development

Testing mode makes development faster and cheaper without changing production behavior.

---

**Last Updated**: 2025-12-18  
**Status**: ✅ Production Ready
