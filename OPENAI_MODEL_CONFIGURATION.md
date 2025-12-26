# OpenAI Model Configuration Guide

This document explains how the podcast-maker system handles different OpenAI models and their respective API endpoints.

## Overview

OpenAI provides three main types of API endpoints for text generation:

1. **Chat Completions** (`/v1/chat/completions`): Used for conversational models like GPT-3.5, GPT-4, etc.
2. **Responses API** (`/v1/responses`): Used for advanced models like GPT-5.2-pro with extended capabilities (web search, reasoning, etc.)
3. **Completions** (`/v1/completions`): Legacy endpoint for older completion-based models

The system automatically selects the correct endpoint based on the model being used.

## Model-to-Endpoint Mapping

The model-to-endpoint mapping is configured in `scripts/global_config.py`:

```python
OPENAI_MODEL_ENDPOINTS = {
    "gpt-3.5-turbo": "chat",
    "gpt-3.5-turbo-16k": "chat",
    "gpt-4": "chat",
    "gpt-4-turbo": "chat",
    "gpt-4-turbo-preview": "chat",
    "gpt-4o": "chat",
    "gpt-4o-mini": "chat",
    "gpt-5-mini": "chat",
    "gpt-5.2-pro": "responses",  # Uses /v1/responses endpoint (Responses API)
}
```

### Adding New Models

To add support for a new model:

1. Open `scripts/global_config.py`
2. Add the model to the `OPENAI_MODEL_ENDPOINTS` dictionary:
   - Use `"chat"` for models that support the chat completions endpoint
   - Use `"responses"` for models that require the Responses API endpoint (with web search, reasoning, etc.)
   - Use `"completion"` for legacy models that require the completions endpoint
3. Save the file - no other changes are needed

Example:
```python
"gpt-6-ultra": "chat",  # Hypothetical future model
"gpt-5.3-pro": "responses",  # Advanced model with Responses API
```

## How It Works

### 1. Endpoint Selection

The `get_openai_endpoint_type()` function in `global_config.py` determines which endpoint to use:

```python
def get_openai_endpoint_type(model: str) -> str:
    """Get the OpenAI API endpoint type for a given model."""
    return OPENAI_MODEL_ENDPOINTS.get(model, "chat")  # Defaults to "chat"
```

### 2. Dynamic API Calls

The `openai_utils.py` module provides wrapper functions that handle both endpoint types:

- `create_openai_completion()`: Creates completions using the appropriate endpoint
- `extract_completion_text()`: Extracts text from responses regardless of endpoint
- `get_finish_reason()`: Gets the finish reason from responses

### 3. Integration

All script generation modules use these wrapper functions:

- `scripts/script_generate.py`: Single-format script generation
- `scripts/multi_format_generator.py`: Multi-format batch generation
- `scripts/responses_api_generator.py`: Responses API with web search

## Configuration Options

### Environment Variables

- `GPT_KEY` or `OPENAI_API_KEY`: Your OpenAI API key (required)
- `RESPONSES_API_MODEL`: Override the default model for Responses API (default: `gpt-5.2-pro`)

### Global Configuration

In `scripts/global_config.py`:

```python
GPT_MODEL = "gpt-5.2-pro"  # Default model for script generation
MAX_COMPLETION_TOKENS = 32000  # Maximum tokens per response
```

## Endpoint Differences

### Chat Completions Endpoint

**Format:**
```python
client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    max_completion_tokens=1000
)
```

**Features:**
- Supports multi-turn conversations
- System messages for instruction
- Tool calling (e.g., web_search)
- Structured message format

### Responses API Endpoint

**Format:**
```python
client.responses.create(
    model="gpt-5.2-pro",
    input="Write a long output...",
    max_output_tokens=60000,
    reasoning={"effort": "medium"},
    tools=[{"type": "web_search"}]
)
```

**Features:**
- Extended output length (up to 60,000 tokens)
- Web search integration for real-time fact checking
- Reasoning capability with configurable effort
- Tool calling support (web_search, etc.)
- Optimized for long-form content generation
- Uses `input` field instead of `prompt`
- Uses `max_output_tokens` instead of `max_tokens`
- **Does NOT support `temperature` parameter** - this parameter is not available for Responses API models

### Completions Endpoint (Legacy)

**Format:**
```python
client.completions.create(
    model="gpt-3.5-turbo-instruct",
    prompt="Hello!",
    max_tokens=1000
)
```

**Features:**
- Simple prompt-response format
- Single-turn completion
- No tool calling support
- Uses `max_tokens` instead of `max_completion_tokens`
- Legacy endpoint for older models

## Error Handling

The system includes several error handling mechanisms:

1. **Invalid Model Configuration**: If a model is not in the mapping, it defaults to the chat endpoint
2. **Missing Parameters**: Raises `ValueError` if required parameters are missing for the endpoint type
3. **Tool Warning**: Logs a warning if tools are specified for completion models (not supported)

## Testing

To test with different models:

1. Set the desired model in your topic configuration or environment variable
2. Run the pipeline: `python scripts/run_pipeline.py --topic topic-01`
3. Check the logs for endpoint selection: `"Using completion endpoint for model: gpt-5.2-pro"`

## Troubleshooting

### Common Issues

**Issue**: Model not found or invalid API response
- **Solution**: Verify the model name in `OPENAI_MODEL_ENDPOINTS` matches the actual model name used by OpenAI

**Issue**: Tools not working with completion models
- **Solution**: Legacy completion models don't support tools. Use a chat model or Responses API model (like gpt-5.2-pro) if you need web_search or other tools

**Issue**: 404 Not Found error with gpt-5.2-pro
- **Solution**: Make sure gpt-5.2-pro is mapped to "responses" endpoint, not "completion" in `OPENAI_MODEL_ENDPOINTS`

**Issue**: Response format errors
- **Solution**: The wrapper functions handle format differences automatically. If errors persist, check the logs for endpoint type mismatch

**Issue**: 400 Bad Request - "Unsupported parameter: 'temperature' is not supported with this model"
- **Solution**: This error occurs when using a Responses API model (like gpt-5.2-pro) with the `temperature` parameter. The Responses API does not support the `temperature` parameter. The code has been updated to automatically exclude this parameter for Responses API models. If you see this error, ensure you're using the latest version of `openai_utils.py` and `responses_api_generator.py`

## Architecture Notes

The dynamic endpoint selection system provides:

1. **Flexibility**: Easy to add new models without changing code
2. **Maintainability**: Centralized configuration in one place
3. **Compatibility**: Backward compatible with existing scripts
4. **Safety**: Graceful degradation with default endpoint selection

## References

- [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [OpenAI Completions API](https://platform.openai.com/docs/api-reference/completions) (Legacy)
- Global Configuration: `scripts/global_config.py`
- Utility Functions: `scripts/openai_utils.py`
