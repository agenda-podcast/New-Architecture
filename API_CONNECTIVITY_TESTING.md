# API Connectivity Testing Guide

This guide explains how to test API connections used by the podcast maker to verify that credentials and endpoints are properly configured.

## Overview

The podcast maker uses three main APIs:
1. **OpenAI API** - For script generation using GPT models
2. **Google Custom Search API** - For image collection
3. **Google Cloud Text-to-Speech API** - For premium TTS

Each API has a dedicated connectivity test that validates credentials and endpoints with minimal cost.

## Running Tests

### Via GitHub Actions (Recommended)

The easiest way to test API connectivity is through the GitHub Actions workflow:

1. Go to your repository on GitHub
2. Navigate to **Actions** → **API Connectivity Tests**
3. Click **Run workflow**
4. Select which API to test:
   - **all** - Test all APIs together (recommended)
   - **openai** - Test only OpenAI API
   - **google-search** - Test only Google Custom Search API
   - **google-tts** - Test only Google Cloud TTS API
5. Click **Run workflow** to start the test

The workflow uses the **Main** environment to access your API credentials stored as secrets.

### Via Command Line (Local Testing)

You can also run tests locally to verify your development environment:

#### Test All APIs
```bash
cd scripts
python test_all_api_connectivity.py
```

#### Test Individual APIs
```bash
# Test OpenAI API
python test_openai_connectivity.py

# Test Google Custom Search API
python test_google_search_connectivity.py

# Test Google Cloud TTS API
python test_google_tts_connectivity.py
```

**Prerequisites:**
- Python 3.11 or higher
- Required packages installed: `pip install -r requirements.txt`
- Environment variables set with your API credentials

#### Setting Environment Variables for Local Testing

```bash
# Required for OpenAI test
export GPT_KEY="your-openai-api-key"

# Required for Google Search test
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-google-search-api-key"
export GOOGLE_SEARCH_ENGINE_ID="your-search-engine-id"

# Required for Google TTS test
export GOOGLE_API_KEY="your-google-cloud-api-key"
```

## Test Details

### OpenAI API Test

**What it tests:**
- API credentials are valid
- OpenAI service is accessible
- Client can make successful requests

**Method:**
- Sends a minimal request using `gpt-3.5-turbo` model
- Uses only 5 tokens to minimize cost
- Returns a simple response to verify connectivity

**Cost:** ~$0.0001 (less than one hundredth of a cent)

**Common Issues:**
- Invalid API key → Check your key at https://platform.openai.com/api-keys
- Rate limit exceeded → Wait a moment and retry
- Network timeout → Check internet connection

### Google Custom Search API Test

**What it tests:**
- API credentials are valid
- Search Engine ID is configured correctly
- Google Custom Search service is accessible

**Method:**
- Performs a simple search query with 1 result
- Uses a generic test query: "test"
- Validates response structure

**Cost:** Free (uses 1 of 100 free daily queries)

**Common Issues:**
- 403 error → Enable Custom Search API at https://console.cloud.google.com/apis/library/customsearch.googleapis.com
- 400 error → Verify Search Engine ID at https://programmablesearchengine.google.com/
- 429 error → Daily quota exceeded, wait until tomorrow

### Google Cloud TTS API Test

**What it tests:**
- API credentials are valid (via Application Default Credentials)
- Google Cloud TTS service is accessible
- Client can retrieve voice information

**Method:**
- Uses `list_voices()` API call (metadata operation)
- Lists available TTS voices
- Does NOT synthesize any speech

**Cost:** Free (metadata API call, no quota usage)

**Authentication Note:** 
- Google Cloud TTS uses **Application Default Credentials (ADC)**, not API keys
- The `GOOGLE_API_KEY` environment variable is checked for reference, but authentication happens through ADC
- ADC looks for credentials in this order:
  1. `GOOGLE_APPLICATION_CREDENTIALS` environment variable (service account JSON file)
  2. User credentials from gcloud CLI
  3. Compute Engine/GKE metadata server
- For GitHub Actions, the secret should contain a service account JSON or be configured appropriately

**Note:** This test uses a free metadata API call that doesn't count against your TTS quota. It validates credentials without incurring any charges.

**Common Issues:**
- 401/403 error → Check credentials and enable TTS API at https://console.cloud.google.com/apis/library/texttospeech.googleapis.com
- Network timeout → Check internet connection
- Permission denied → Verify service account has TTS permissions
- Default credentials not found → Ensure GOOGLE_APPLICATION_CREDENTIALS points to service account JSON or ADC is configured

## Automated Testing

### Weekly Schedule

The API connectivity tests run automatically every Monday at 08:00 UTC to:
- Detect expired or invalid credentials early
- Ensure APIs remain accessible
- Catch configuration issues before podcast generation

### Test Results

After running tests, check:
1. **GitHub Actions** page for workflow run status
2. **Workflow logs** for detailed test output
3. **Step Summary** for a quick overview of results

## Troubleshooting

### All Tests Fail

**Possible causes:**
- Secrets not configured in GitHub environment
- Network connectivity issues
- API service outages

**Solutions:**
1. Verify secrets are set in **Settings** → **Environments** → **Main**
2. Check API service status pages
3. Retry after a few minutes

### Specific Test Fails

1. Check the test output for specific error messages
2. Follow the guidance provided in the error message
3. Verify the corresponding secret is correctly set
4. Ensure the API is enabled in the appropriate console

### Cost Concerns

All connectivity tests are designed to use minimal resources:
- **Total cost for all tests:** < $0.001 (less than one tenth of a cent)
- **Google TTS test:** Completely free (metadata call only)
- **Google Search test:** Free (uses free daily quota)
- **OpenAI test:** ~$0.0001 (minimal tokens)

Running tests daily would cost less than $0.04 per month.

## Best Practices

1. **Run tests before production deployments** to ensure all APIs are working
2. **Run tests after updating credentials** to verify new keys work correctly
3. **Monitor test results** in automated runs to catch issues early
4. **Use individual tests** when troubleshooting a specific API
5. **Review logs carefully** when tests fail for detailed error information

## Integration with CI/CD

The API connectivity tests can be integrated into your CI/CD pipeline:

```yaml
# Example: Run tests before podcast generation
jobs:
  test-apis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Test API connectivity
        run: |
          cd scripts
          python test_all_api_connectivity.py
  
  generate-podcast:
    needs: test-apis
    runs-on: ubuntu-latest
    steps:
      # ... podcast generation steps
```

## Additional Resources

- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Google Custom Search API Documentation](https://developers.google.com/custom-search/v1/overview)
- [Google Cloud TTS API Documentation](https://cloud.google.com/text-to-speech/docs)
- [Environment Setup Guide](./ENVIRONMENT_SETUP.md)

## Support

If tests consistently fail or you encounter issues:

1. Check the test logs for detailed error messages
2. Verify all secrets are correctly configured
3. Ensure APIs are enabled in their respective consoles
4. Check that API keys have not expired
5. Verify billing is enabled for paid APIs (if applicable)
