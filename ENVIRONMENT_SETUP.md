# Environment Setup Guide

## GitHub Environment Configuration

This project uses GitHub Environments to manage secrets securely. The **Main** environment must be configured with the following secrets.

### Setting Up the Main Environment

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Environments**
3. Create or select the **Main** environment
4. Add the following secrets:

### Required Secrets in Main Environment

#### 1. GPT_KEY (REQUIRED)
- **Purpose**: OpenAI API key for ChatGPT script generation
- **Used by**: `scripts/script_generate.py`, `scripts/multi_format_generator.py`
- **Get from**: [OpenAI API Keys](https://platform.openai.com/api-keys)
- **Model used**: `gpt-5-mini` for deep conversational scripts
- **Required**: Yes - Pipeline will fail if not set

#### 2. GOOGLE_API_KEY (REQUIRED for premium topics)
- **Purpose**: Google Cloud API key for Gemini TTS (Text-to-Speech)
- **Used by**: `scripts/tts_generate.py` for topics with `"premium_tts": true`
- **Get from**: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- **API to enable**: [Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
- **Required**: Yes for premium topics - Pipeline will fail if not set and `"premium_tts": true`
- **Note**: Not required if `"premium_tts": false` (uses Piper TTS instead)

#### 3. GOOGLE_CUSTOM_SEARCH_API_KEY (REQUIRED)
- **Purpose**: Google Custom Search API key for fetching real articles
- **Used by**: `scripts/collect_sources.py` to dynamically find articles
- **Get from**: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- **API to enable**: [Custom Search API](https://console.cloud.google.com/apis/library/customsearch.googleapis.com)
- **Required**: Yes - Pipeline will fail if not set

#### 4. GOOGLE_SEARCH_ENGINE_ID (REQUIRED)
- **Purpose**: Google Custom Search Engine ID
- **Used by**: `scripts/collect_sources.py` together with GOOGLE_CUSTOM_SEARCH_API_KEY
- **Get from**: [Programmable Search Engine](https://programmablesearchengine.google.com/)
- **Setup**: Create a search engine configured to search the entire web
- **Required**: Yes - Pipeline will fail if not set

## TTS Provider Selection

The system supports two TTS providers:

### 1. Piper TTS (Local, Free)
- **When used**: Automatically when `"premium_tts": false` in topic config
- **Voices**: Downloaded from Piper repository on first run
- **Quality**: Good quality, offline capable
- **Cost**: Free
- **Configuration**: Set `"premium_tts": false` in `topics/topic-XX.json`

### 2. Google Cloud TTS (Premium)
- **When used**: Only when `"premium_tts": true` in topic config AND `GOOGLE_API_KEY` is set
- **Voices**: Cloud-based Wavenet/Journey voices
- **Quality**: Premium quality with natural intonation
- **Cost**: Pay per character (see Google Cloud pricing)
- **Configuration**: Set `"premium_tts": true` in `topics/topic-XX.json`

**Important**: The TTS provider is forced based on the `premium_tts` setting. Even if `GOOGLE_API_KEY` is available, Piper will be used when `premium_tts` is false. This ensures predictable behavior and cost control.

## Article Fetching

### Google Custom Search API (REQUIRED)
The pipeline requires both `GOOGLE_CUSTOM_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID` to be configured:
- Real articles are fetched from Google Custom Search
- URLs are validated and accessible
- Article content is extracted and used for script generation
- **Pipeline will fail if these credentials are not set**

**Production Requirement**: Both API credentials must be configured for the pipeline to run successfully. The system no longer falls back to mock or placeholder data.

## Local Development Setup

For local testing, set all required environment variables:

```bash
# REQUIRED: For script generation
export GPT_KEY="your-openai-api-key"

# REQUIRED: For article fetching
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-google-custom-search-api-key"
export GOOGLE_SEARCH_ENGINE_ID="your-search-engine-id"

# REQUIRED if using premium_tts: true in topic config
export GOOGLE_API_KEY="your-google-cloud-api-key"
```

**Note**: All required environment variables must be set or the pipeline will fail with explicit error messages.

Then run the pipeline:
```bash
cd scripts
python run_pipeline.py --topic topic-01
```

## Troubleshooting

### Issue: "Incorrect API key provided" for OpenAI
- **Cause**: `GPT_KEY` secret not set or incorrect in Main environment
- **Solution**: Verify the secret is set correctly in GitHub Settings → Environments → Main

### Issue: "Google Custom Search API credentials not configured"
- **Cause**: Missing `GOOGLE_CUSTOM_SEARCH_API_KEY` or `GOOGLE_SEARCH_ENGINE_ID`
- **Solution**: Add both secrets to Main environment - they are required for pipeline operation

### Issue: "Failed to generate TTS using Google Cloud TTS"
- **Cause**: Missing or invalid `GOOGLE_API_KEY` for premium topics
- **Solution**: Add `GOOGLE_API_KEY` to Main environment or set `"premium_tts": false` in topic config

### Issue: "Voice models not found"
- **Cause**: Piper voices not available in cache
- **Solution**: Voice models are cached and should be automatically restored from GitHub Actions cache

## Cost Control

To minimize costs during testing:

1. **Disable premium TTS**: Set `"premium_tts": false` in all topic configs (uses free Piper TTS)
2. **Limit topics**: Set `"enabled": false` for topics you're not testing
3. **Reduce queries**: Use single query per topic instead of multiple
4. **Manual runs**: Use workflow_dispatch instead of scheduled runs
5. **Monitor API usage**: Regularly check your API usage in Google Cloud and OpenAI consoles

**Note**: All API credentials are required for production use. The pipeline will fail explicitly if any required credentials are missing.

## Workflow Jobs and Environment

The GitHub Actions workflow (`daily.yml`) has the following jobs that use the Main environment:

- **collect**: Uses `GOOGLE_CUSTOM_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`
- **run**: Uses `GPT_KEY` and `GOOGLE_API_KEY`

Both jobs are configured with `environment: Main` to access secrets from the Main environment.
