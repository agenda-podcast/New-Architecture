# Architecture Simplification: Source Collection Separation

**Date**: 2025-12-17  
**Change**: Separate Google Search (images) from OpenAI (content generation)  
**Impact**: Simpler pipeline, leverages OpenAI web_search directly

---

## Previous Architecture

**Old Flow**:
```
1. Google Custom Search API → Collect sources with text + images
2. Parse and store sources → data/*/fresh.json
3. Load sources → Send to OpenAI
4. OpenAI generates scripts from provided sources
5. Extract images from sources for video
```

**Problems**:
- Redundant search (Google + OpenAI both searching)
- Complex source management (storage, dedup, freshness)
- Token overhead (sending sources to OpenAI)
- Tight coupling between collection and generation

---

## New Architecture

**New Flow**:
```
1. OpenAI web_search → Finds and verifies sources directly
2. OpenAI generates scripts from web_search results
3. Google Custom Search API → ONLY for images (parallel or after)
4. Extract images for video rendering
```

**Benefits**:
- ✅ Simpler pipeline (fewer steps)
- ✅ No redundant searches
- ✅ Leverages OpenAI's built-in web_search
- ✅ Reduced token usage (no sources sent)
- ✅ Always fresh sources (OpenAI searches real-time)
- ✅ Loose coupling (images independent of content)

---

## Component Responsibilities

### OpenAI Responses API (Content Generation)

**Purpose**: Generate podcast scripts with verified facts

**Input**: 
- Topic title
- Topic description
- Freshness window
- Region preference
- Content type specifications

**Process**:
1. Use web_search tool to find latest news on topic
2. Verify facts from search results
3. Generate all content formats (L, M, S, R)
4. Include citations from web_search sources

**Output**:
- Complete scripts for all content types
- Verified facts and citations
- Consistent narrative across formats

**No Longer Receives**:
- ❌ Pre-collected sources
- ❌ Article text/summaries
- ❌ Source metadata

### Google Custom Search API (Image Collection)

**Purpose**: Collect images ONLY for video generation

**Input**:
- Topic queries
- Search filters (language, region)
- Freshness window

**Process**:
1. Search for articles on topic
2. Extract image URLs (OpenGraph, CSE)
3. Store images for video rendering

**Output**:
- Image URLs
- Article metadata (optional, for attribution)

**No Longer Used For**:
- ❌ Content generation
- ❌ Script writing
- ❌ Fact verification

---

## Pipeline Comparison

### Old Pipeline

```python
# Step 1: Collect sources (for content + images)
collect_sources.py --topic topic-01
# → data/topic-01/fresh.json (sources with text + images)

# Step 2: Generate scripts (uses collected sources)
script_generate.py --topic topic-01
# Loads fresh.json, sends sources to OpenAI
# → outputs/topic-01/*.script.json

# Step 3: Generate audio
tts_generate.py --topic topic-01
# → outputs/topic-01/*.mp3

# Step 4: Render video (uses images from sources)
video_render.py --topic topic-01
# Loads fresh.json for images
# → outputs/topic-01/*.mp4
```

### New Pipeline

```python
# Step 1: Generate scripts (OpenAI searches directly)
script_generate.py --topic topic-01 --use-responses-api
# OpenAI web_search finds sources
# → outputs/topic-01/*.script.json (with citations)

# Step 2: Collect images (parallel or after scripts)
collect_sources.py --topic topic-01 --images-only
# → data/topic-01/images.json (image URLs only)

# Step 3: Generate audio
tts_generate.py --topic topic-01
# → outputs/topic-01/*.mp3

# Step 4: Render video (uses collected images)
video_render.py --topic topic-01
# Loads images.json
# → outputs/topic-01/*.mp4
```

**Key Differences**:
- Scripts no longer depend on collected sources
- Image collection can run in parallel or after scripts
- Simpler data flow

---

## Code Changes

### collect_sources.py

**Updated Purpose**: Image collection only

```python
"""
Collect sources for podcast topics - USED FOR IMAGE COLLECTION ONLY.

IMPORTANT: This module collects sources from Google Custom Search API
primarily for IMAGE URLs needed for video generation.

Script generation uses OpenAI's web_search tool directly and does NOT
rely on these collected sources for content generation.
"""

def collect_for_topic(topic_id: str) -> Dict[str, Any]:
    """
    Collect sources with images for video generation.
    
    NOTE: These sources are NOT sent to OpenAI for script generation.
    OpenAI uses web_search tool to find sources directly.
    """
    # Search Google for articles
    sources = search_sources_google(query, languages, regions)
    
    # Filter sources with images
    sources_with_images = [s for s in sources if s.get('image')]
    
    # Save for video rendering
    save_sources_for_images(sources_with_images)
```

### responses_api_generator.py

**Updated**: No sources passed to OpenAI

```python
def generate_all_content_batch(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate ALL content types using OpenAI web_search.
    
    IMPORTANT: We do NOT send collected sources to OpenAI.
    OpenAI will use web_search tool to find sources directly.
    """
    # Generate prompt with ONLY topic information
    input_prompt = generate_batch_responses_api_input(
        topic=config['title'],
        topic_description=config['description'],
        freshness_window=f"last {config['freshness_hours']} hours",
        region=config['search_regions'][0],
        rumors_allowed=config.get('rumors_allowed', False),
        content_specs=content_specs
    )
    
    # Call OpenAI - it will search directly
    response = client.chat.completions.create(
        model="gpt-5.2-pro",
        tools=[{"type": "web_search"}],  # OpenAI searches itself
        messages=[
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": input_prompt}  # No sources!
        ]
    )
```

### System Instructions

**Updated**: Emphasizes direct searching

```python
RESPONSES_API_INSTRUCTIONS = """
CRITICAL: You will receive ONLY a topic prompt - no pre-collected sources. 
You MUST use the web_search tool to find and verify ALL information yourself.

Core requirements:
- You MUST use web_search to find latest information on the topic
- You will NOT receive pre-collected sources
- Search for news within the provided Freshness Window
- Do NOT rely on training data for current events
```

---

## Benefits Analysis

### 1. Simplified Pipeline

**Before**:
- Collect sources → Store → Load → Send to OpenAI → Generate

**After**:
- OpenAI searches directly → Generate

**Reduction**: 3 steps removed from critical path

### 2. Reduced Token Usage

**Before**:
```python
input_tokens = (
    system_prompt +        # ~1,000 tokens
    topic_context +        # ~500 tokens
    sources_text +         # ~5,000 tokens (10 sources × 500)
    content_specs          # ~1,000 tokens
)
# Total: ~7,500 input tokens
```

**After**:
```python
input_tokens = (
    system_prompt +        # ~1,000 tokens
    topic_context +        # ~500 tokens
    content_specs          # ~1,000 tokens
)
# Total: ~2,500 input tokens
```

**Savings**: 67% reduction in input tokens

### 3. Always Fresh Sources

**Before**:
- Collect sources at time T0
- Generate script at time T1 (hours/days later)
- Sources may be stale

**After**:
- OpenAI searches at generation time
- Always latest information
- No staleness issues

### 4. Better Source Quality

**Before**:
- Limited to Google CSE results
- Fixed search queries
- May miss breaking news

**After**:
- OpenAI can search dynamically
- Can refine queries based on context
- Can search multiple times if needed
- Better at finding latest breaking news

### 5. Simpler Caching

**Before**:
```python
# Cache sources separately
cache_sources(query, sources)

# Cache OpenAI responses
cache_llm_response(prompt, response)
```

**After**:
```python
# Only cache OpenAI responses (includes sources)
cache_llm_response(prompt, response)
```

**Simpler**: Single cache layer

---

## Migration Guide

### For Existing Code

**Script Generation**:
```python
# OLD - Don't do this anymore
sources = load_sources_from_file('data/topic-01/fresh.json')
script = generate_script_with_sources(config, sources)

# NEW - Just topic info
script = generate_all_content_with_responses_api(config)
# OpenAI searches internally via web_search
```

**Image Collection**:
```python
# Still needed for video generation
collect_sources.py --topic topic-01

# But understand it's ONLY for images now
# Scripts don't use these sources
```

### For Workflows

**Old Workflow**:
```yaml
- name: Collect Sources
  run: python collect_sources.py --all
  
- name: Generate Scripts
  run: python script_generate.py --all
  needs: collect-sources  # Must run after
```

**New Workflow**:
```yaml
- name: Generate Scripts
  run: python script_generate.py --all --use-responses-api
  # No dependency on source collection!
  
- name: Collect Images
  run: python collect_sources.py --all --images-only
  # Can run in parallel or after
```

---

## Cost Analysis

### Token Cost Comparison

**Per Topic Generation** (15 content pieces):

**Old Approach**:
```
Input tokens:  7,500 (with sources)
Output tokens: 25,000 (all content)
Cost: (7.5 × $0.10) + (25 × $0.30) = $8.25
```

**New Approach**:
```
Input tokens:  2,500 (no sources)
Output tokens: 25,000 (all content)
Web search: ~1,000 tokens (included in input)
Cost: (3.5 × $0.10) + (25 × $0.30) = $7.85
```

**Savings per topic**: $0.40 (5%)

**For 100 topics/month**: $40 savings

### API Calls Comparison

**Old Approach**:
- Google CSE: 1 call per topic
- OpenAI: 1 call per topic (batch)
- **Total**: 2 API calls per topic

**New Approach**:
- OpenAI: 1 call per topic (batch, includes search)
- Google CSE: 1 call per topic (images only, can be parallel)
- **Total**: 1-2 API calls (images optional/parallel)

**Same or better**: No increase in API calls

---

## Testing

### Validate Web Search Usage

```python
# Test that OpenAI actually uses web_search
response = generate_all_content_batch(config)

# Check for web search citations
for content in response['content']:
    assert 'sources' in content.get('metadata', {}), \
        "Content should have sources from web_search"
    
    sources = content['metadata']['sources']
    assert len(sources) > 0, \
        "Should have at least some web_search sources"
    
    # Verify sources are recent
    for source in sources:
        assert is_within_freshness_window(source['published_date']), \
            "Sources should be within freshness window"
```

### Compare Quality

```python
# Generate with old method (sources provided)
old_script = generate_with_sources(config, sources)

# Generate with new method (web_search only)
new_script = generate_with_responses_api(config)

# Compare
print(f"Old sources: {len(sources)}")
print(f"New sources: {len(new_script['metadata']['sources'])}")

# Both should have similar fact coverage
assert similarity(old_script, new_script) > 0.8
```

---

## Rollout Plan

### Phase 1: Implement (Complete)
- ✅ Update responses_api_generator.py
- ✅ Remove source passing from prompts
- ✅ Update system instructions
- ✅ Document changes

### Phase 2: Test (Next)
- [ ] Test with real API credentials
- [ ] Verify web_search is used
- [ ] Check source freshness
- [ ] Compare quality vs old method
- [ ] Validate cost savings

### Phase 3: Parallel Run
- [ ] Run both methods side-by-side
- [ ] Compare outputs
- [ ] Validate accuracy
- [ ] Monitor costs

### Phase 4: Migration
- [ ] Update workflows
- [ ] Update documentation
- [ ] Train team on new flow
- [ ] Remove old code

---

## FAQs

**Q: Why not send sources to OpenAI as additional context?**

A: 
- Adds token cost
- May cause confusion (sources vs web_search results)
- Sources may be stale
- OpenAI web_search is better at finding latest info

**Q: What if OpenAI's web_search misses something?**

A: 
- We can still collect sources separately
- Add them as optional context if needed
- But default should be web_search only

**Q: Do we still need Google CSE at all?**

A: 
- Yes, for IMAGE collection for videos
- OpenAI web_search doesn't provide image URLs
- Google CSE specifically extracts OpenGraph images

**Q: Can we run script generation without collecting sources?**

A: 
- Yes! That's the point
- Script generation is independent now
- Only video rendering needs images

**Q: What about attribution and citations?**

A: 
- OpenAI web_search provides citations
- We save those with the script
- Still have source URLs for attribution

---

## Conclusion

**Architecture simplification** achieved by:
1. ✅ Leveraging OpenAI's built-in web_search
2. ✅ Removing source collection from critical path
3. ✅ Separating concerns (images vs content)
4. ✅ Reducing token usage (67%)
5. ✅ Simplifying pipeline (fewer steps)

**Result**: Simpler, faster, cheaper, more maintainable system.

---

## Related Files

- `scripts/responses_api_generator.py` - Updated (no sources)
- `scripts/collect_sources.py` - Updated (images only)
- `BATCH_OPTIMIZATION_SUMMARY.md` - Batch optimization details
- `RESPONSES_API_IMPLEMENTATION.md` - Full API guide

---

**Status**: ✅ **Implementation Complete**  
**Next Step**: Test with real API to verify web_search usage  
**Expected Impact**: 67% reduction in input tokens, simpler pipeline

---

**Last Updated**: 2025-12-17
