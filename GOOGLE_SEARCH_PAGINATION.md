# Google Custom Search API Pagination Implementation

## Overview

This document describes the pagination implementation for Google Custom Search API image collection, which allows fetching up to 100 results per query instead of just 10.

## What Changed

### 1. Configuration (`scripts/global_config.py`)

Added three new constants:

```python
GOOGLE_SEARCH_DAILY_LIMIT = 1000  # Maximum API results per day (up to 1000)
GOOGLE_SEARCH_MAX_RESULTS_PER_QUERY = 100  # Maximum results per query (API limit)
GOOGLE_SEARCH_RESULTS_PER_PAGE = 10  # Results per page (API hard limit)
```

### 2. Usage Tracking (`scripts/image_collector.py`)

Added daily usage tracking functionality:

- **Tracking File**: `~/.podcast-maker/google_search_usage.json`
- **Format**: `{"date": "2025-12-19", "count": 150}`
- **Auto-reset**: Counter resets at midnight
- **Functions**:
  - `get_daily_usage()`: Get current usage count
  - `update_daily_usage(results)`: Update usage after API call
  - `check_daily_limit(requested)`: Check if request fits within limit

### 3. Pagination Logic (`scripts/image_collector.py`)

The image collection now supports pagination:

```python
# Before: Single API call per query (max 10 results)
result = service.cse().list(q=query, num=10).execute()

# After: Multiple API calls with pagination (up to 100 results)
start_index = 1
while len(results) < target and start_index <= 91:
    result = service.cse().list(
        q=query, 
        num=10,
        start=start_index  # Pagination parameter
    ).execute()
    
    # Use nextPage for next iteration
    next_page = result.get('queries', {}).get('nextPage', [])
    if next_page:
        start_index = next_page[0]['startIndex']
```

## How It Works

### Example: Requesting 30 Images

1. **Initial Check**:
   - Check daily usage: 50/1000 used
   - Available: 950 results
   - Request fits: ✓

2. **Query Processing**:
   - Query 1: "Donald Trump"
     - Page 1: start=1, gets 10 results
     - Page 2: start=11, gets 10 results
     - Page 3: start=21, gets 10 results
     - Total: 30 images

3. **Usage Update**:
   - Update daily counter: 50 → 80
   - Save to tracking file

4. **Download Images**:
   - Download all 30 images to disk
   - Return list of downloaded files

### Example: Daily Limit Reached

```bash
$ python scripts/image_collector.py --topic topic-01 --num-images 30

Daily usage: 995/1000 results used today
⚠ Only 5 results available within daily limit (requested: 30)
Searching for images: 'Donald J Trump'
  Found image 1: Donald Trump at rally
  Found image 2: Trump family photo
  ...
  Found image 5: Melania Trump portrait
  Daily limit reached during pagination

Total API results used: 5
✓ Successfully collected 5 images
```

## API Quota Details

### Google Custom Search API Limits

- **Free Tier**: 100 queries/day (not results!)
- **Each page request**: 1 query
- **Results per page**: 10 (hard limit)
- **Maximum results**: 100 per query (10 pages)

### Our Implementation Limits

- **Daily Results Limit**: 1000 (configurable)
- **Maximum per Query**: 100 results
- **Tracking**: Per result, not per query
- **Reset**: Automatic at midnight

### Example Usage Scenarios

| Scenario | Images Requested | API Calls | Results Used | Queries Used |
|----------|-----------------|-----------|--------------|--------------|
| Small collection | 10 | 1 | 10 | 1 |
| Medium collection | 30 | 3 | 30 | 3 |
| Large collection | 100 | 10 | 100 | 10 |
| Multiple topics (5×10) | 50 | 5 | 50 | 5 |

## Configuration

### Change Daily Limit

Edit `scripts/global_config.py`:

```python
# For free tier (100 queries/day)
GOOGLE_SEARCH_DAILY_LIMIT = 1000  # Max 1000 results (100 queries × 10 results)

# For paid tier (custom limits)
GOOGLE_SEARCH_DAILY_LIMIT = 5000  # Higher limit
```

### Check Current Usage

```bash
# View tracking file
cat ~/.podcast-maker/google_search_usage.json

# Output: {"date": "2025-12-19", "count": 350}
```

### Reset Usage (Testing Only)

```bash
# Remove tracking file
rm ~/.podcast-maker/google_search_usage.json

# Or set to zero
echo '{"date": "2025-12-19", "count": 0}' > ~/.podcast-maker/google_search_usage.json
```

## Testing

### Unit Tests

```bash
# Run pagination tests
python scripts/test_image_pagination.py

# Tests:
# ✓ Daily usage tracking
# ✓ Daily limit checking
# ✓ Date reset logic
```

### Manual Testing

```bash
# Test with small collection
python scripts/image_collector.py --topic topic-01 --num-images 10

# Test with pagination (30 images = 3 pages)
python scripts/image_collector.py --topic topic-01 --num-images 30

# Test daily limit (set usage near limit first)
echo '{"date": "2025-12-19", "count": 990}' > ~/.podcast-maker/google_search_usage.json
python scripts/image_collector.py --topic topic-01 --num-images 30
# Should limit to 10 images (only 10 results remaining)
```

## Best Practices

1. **Request Only What You Need**:
   - 10-15 images usually sufficient for most videos
   - Don't request 100 if you only need 10

2. **Monitor Daily Usage**:
   - Check `~/.podcast-maker/google_search_usage.json` regularly
   - Stay within free tier limits (1000 results = 100 queries)

3. **Use Caching**:
   - Images are cached in `outputs/{topic}/images/`
   - Reprocessing topics doesn't use quota

4. **Optimize Queries**:
   - Use specific queries for better results
   - Fewer queries with better terms > many generic queries

5. **Paid Tier Considerations**:
   - If exceeding free tier regularly, upgrade to paid
   - Adjust `GOOGLE_SEARCH_DAILY_LIMIT` accordingly
   - $5 per 1,000 queries = ~10,000 results

## Troubleshooting

### "Daily limit reached"

**Cause**: Used all available results for today  
**Solution**: 
1. Wait until midnight for automatic reset
2. Reduce images per topic
3. Use cached images
4. Check usage: `cat ~/.podcast-maker/google_search_usage.json`

### "No nextPage in response"

**Cause**: Reached end of available results  
**Solution**: This is normal - no more results available for the query

### Pagination not working

**Cause**: Possible issues with API response  
**Solution**:
1. Check API credentials
2. Verify search engine configuration
3. Check logs for error messages

## Summary

The pagination implementation provides:

- ✅ Up to 100 results per query (vs 10 before)
- ✅ Automatic daily limit tracking and enforcement
- ✅ Protection against unexpected quota usage
- ✅ Dynamic pagination using `queries.nextPage`
- ✅ Graceful handling of limits and errors
- ✅ Comprehensive logging and error messages

This ensures reliable image collection while staying within API quotas and avoiding unexpected charges.
