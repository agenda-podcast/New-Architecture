# Image Collection Setup Guide

This document explains how to set up and use the Google Custom Search API for image collection.

---

## Overview

Images for video generation are now collected using **Google Custom Search API** instead of being extracted from pre-collected sources. This provides better image quality and reliability.

---

## Prerequisites

1. **Google Cloud Account**: You need a Google Cloud account
2. **Google Custom Search API**: Enable the Custom Search API in Google Cloud Console
3. **Programmable Search Engine**: Create a search engine ID

---

## Setup Instructions

### Step 1: Enable Google Custom Search API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** > **Library**
4. Search for "Custom Search API"
5. Click **Enable**

### Step 2: Create API Key

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **API Key**
3. Copy the API key (you'll need this)
4. **Important**: Restrict the key to "Custom Search API" for security

### Step 3: Create Programmable Search Engine

1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/controlpanel/all)
2. Click **Add** to create a new search engine
3. Configure:
   - **Sites to search**: Select "Search the entire web"
   - **Name**: Give it a descriptive name (e.g., "Podcast Image Search")
4. Click **Create**
5. Copy the **Search engine ID** (format: `xxxxxxxxxxxxxx:yyyyyyyyyy`)

### Step 4: Configure Environment Variables

Set the following environment variables:

```bash
# OpenAI API key (for script generation)
export GPT_KEY="sk-..."

# Google Custom Search API credentials (for image collection)
export GOOGLE_CUSTOM_SEARCH_API_KEY="AIza..."
export GOOGLE_SEARCH_ENGINE_ID="xxxxxxxxxxxxxx:yyyyyyyyyy"
```

For GitHub Actions, add these as repository secrets:
- `GPT_KEY`
- `GOOGLE_CUSTOM_SEARCH_API_KEY`
- `GOOGLE_SEARCH_ENGINE_ID`

---

## Usage

### Automatic (via Pipeline)

Images are collected automatically when you run the pipeline:

```bash
python scripts/run_pipeline.py --topic topic-01
```

The pipeline will:
1. Generate scripts using two-pass architecture
2. **Collect images using Google Custom Search API** (10 images by default)
3. Generate TTS audio
4. Render videos with collected images

### Manual (Standalone)

You can also collect images separately:

```bash
# Collect images for a specific topic
python scripts/image_collector.py --topic topic-01

# Collect more images
python scripts/image_collector.py --topic topic-01 --num-images 20
```

Images will be saved to: `outputs/{topic-id}/images/`

---

## How It Works

### Image Collection Process

1. **Query Generation**: Uses topic queries from `topics/{topic-id}.json`
2. **Daily Limit Check**: Verifies available quota before starting
3. **API Request with Pagination**: 
   - Searches Google for images matching the queries
   - Automatically paginates through results using `start` parameter
   - Fetches 10 results per page (API maximum)
   - Can retrieve up to 100 results per query
   - Uses `queries.nextPage` for dynamic pagination
4. **Download**: Downloads images to `outputs/{topic-id}/images/`
5. **Usage Tracking**: Updates daily usage counter after each API call
6. **Caching**: Skips collection if images already exist

### Search Configuration

- **Search Type**: Image search only
- **Safe Search**: Active (filters explicit content)
- **Image Size**: Large (for better quality)
- **Number**: 10 images by default (configurable up to 50)
- **Pagination**: Automatic when more images are needed
- **Daily Limit**: 1000 results maximum per day

### Pagination Details

The pagination implementation follows Google's Custom Search API best practices:

1. **First Page** (results 1-10):
   ```
   start=1, num=10
   ```

2. **Second Page** (results 11-20):
   ```
   start=11, num=10
   ```

3. **Subsequent Pages**:
   - Read `queries.nextPage[0].startIndex` from previous response
   - Continue until target number of images is reached
   - Stop at result 91 (to get results 91-100, the API maximum)

Example:
- Request 30 images for a query
- Makes 3 API calls: start=1, start=11, start=21
- Downloads 30 images total
- Updates daily usage counter by 30

### Fallback Behavior

If image collection fails (missing API keys, network error, etc.), the system automatically creates a placeholder image (solid black) for video generation.

---

## API Quota and Pricing

### Free Tier
- **100 queries per day** (free)
- Each topic uses 1-5 queries (depending on number of queries in config)
- ~20-100 topics can be processed per day on free tier

### Paid Tier
- **$5 per 1,000 queries** after free tier
- For high-volume usage, consider upgrading

### Pagination Support
- **Up to 100 results per query** via pagination
- Uses `start` parameter to fetch results beyond the first 10
- Automatically reads `queries.nextPage` for dynamic pagination
- Maximum 10 results per API request (hard API limit)
- Pagination stops at result 100 (API limitation)

### Daily Usage Limits
- **1000 results maximum per day** (configurable in `global_config.py`)
- System tracks daily usage automatically in `~/.podcast-maker/google_search_usage.json`
- Counter resets at midnight
- Prevents exceeding quota and unexpected charges

### Best Practices
- Use specific topic queries (better image results)
- Limit to 3-5 queries per topic
- Request only the number of images you need (default: 10)
- For high-quality videos, consider 20-30 images with pagination
- Images are cached - reusing topics doesn't count against quota
- Monitor daily usage to stay within free tier limits

---

## Troubleshooting

### "Google Custom Search API credentials not found"
**Solution**: Set `GOOGLE_CUSTOM_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID` environment variables

### "google-api-python-client not available"
**Solution**: Install the package:
```bash
pip install google-api-python-client
```

### "API key not valid"
**Solution**: 
1. Check that the API key is correct
2. Verify Custom Search API is enabled in Google Cloud Console
3. Check API key restrictions (should allow Custom Search API)

### "No images found"
**Solution**:
1. Check that search engine ID is correct
2. Verify topic queries are descriptive (in topics/{topic-id}.json)
3. Try adding more specific queries
4. System will use placeholder image as fallback

### Images not downloading
**Solution**:
1. Check internet connection
2. Some image URLs may be inaccessible (system will skip them)
3. System collects multiple images - if some fail, others should succeed

### "Daily limit reached"
**Solution**:
1. Check current usage: `cat ~/.podcast-maker/google_search_usage.json`
2. Wait until midnight for automatic reset
3. Consider adjusting `GOOGLE_SEARCH_DAILY_LIMIT` in `global_config.py` if you have paid tier
4. Reduce number of images requested per topic
5. Use cached images (reprocessing topics doesn't use quota)

### How to check daily usage
```bash
# View current usage
cat ~/.podcast-maker/google_search_usage.json

# Example output:
# {"date": "2025-12-19", "count": 350}
# This means 350 results used today, 650 remaining
```

### How to reset daily usage manually (for testing)
```bash
# Remove the tracking file
rm ~/.podcast-maker/google_search_usage.json

# Or edit it to set count to 0
echo '{"date": "2025-12-19", "count": 0}' > ~/.podcast-maker/google_search_usage.json
```

---

## Configuration

### Topic Configuration

Each topic can have custom queries for image search:

```json
{
  "id": "topic-01",
  "title": "Donald J Trump",
  "queries": [
    "Donald J Trump",
    "Melania Trump",
    "Ivanka Trump"
  ]
}
```

The image collector uses these queries to search for relevant images.

### Global Configuration

Image collection settings in `scripts/global_config.py`:

```python
# Google Custom Search API Settings
GOOGLE_SEARCH_DAILY_LIMIT = 1000  # Maximum API results per day (up to 1000)
GOOGLE_SEARCH_MAX_RESULTS_PER_QUERY = 100  # Maximum results per query (API limit)
GOOGLE_SEARCH_RESULTS_PER_PAGE = 10  # Results per page (API hard limit)
```

Image collection settings in `scripts/image_collector.py`:

```python
DEFAULT_NUM_IMAGES = 10  # Number of images per topic
MAX_NUM_IMAGES = 50      # Maximum images allowed
IMAGE_SEARCH_TIMEOUT = 10  # Timeout for downloads
```

### Daily Usage Tracking

The system automatically tracks daily API usage in:
```
~/.podcast-maker/google_search_usage.json
```

Format:
```json
{
  "date": "2025-12-19",
  "count": 150
}
```

The counter automatically resets at midnight.

---

## File Structure

```
outputs/
└── topic-01/
    ├── images/              # Images collected for topic
    │   ├── image_000.jpg
    │   ├── image_001.jpg
    │   └── ...
    ├── topic-01-20251218-L1.mp3
    ├── topic-01-20251218-L1.mp4    # Video uses images from images/
    └── ...
```

---

## Benefits Over Previous Approach

1. **Higher Quality**: Direct image search vs. extracting from source metadata
2. **More Reliable**: Dedicated API vs. hoping sources have images
3. **Better Control**: Specify exactly which queries to use
4. **Cached**: Images downloaded once, reused for all 15 videos
5. **Fallback**: Graceful degradation if API unavailable

---

## Example: Full Pipeline Run

```bash
# Set environment variables
export GPT_KEY="sk-..."
export GOOGLE_CUSTOM_SEARCH_API_KEY="AIza..."
export GOOGLE_SEARCH_ENGINE_ID="xxxxxxxxxxxxxx:yyyyyyyyyy"

# Run pipeline for topic-01
python scripts/run_pipeline.py --topic topic-01

# Output:
# Step 1: Generating script...
#   Pass A: L1 + canonical_pack (gpt-5.2-pro)
#   Pass B: M1-M2, S1-S4, R1-R8 (gpt-4.1-nano)
#   ✓ Generated 15 scripts
#
# Step 2: Generating TTS audio...
#   ✓ Generated 15 audio files
#
# Step 3: Rendering video...
#   Collecting images using Google Custom Search API...
#   ✓ Successfully collected 10 images
#   ✓ Rendering 15 videos with collected images
#   ✓ All videos complete
```

---

## Support

For issues or questions:
1. Check this documentation
2. Check logs for detailed error messages
3. Verify API keys and configuration
4. Test image collector standalone: `python scripts/image_collector.py --topic topic-01`

---

**Status**: ✅ Ready for production use  
**Last Updated**: 2025-12-18
