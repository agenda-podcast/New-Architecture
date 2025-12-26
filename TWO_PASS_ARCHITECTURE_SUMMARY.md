# Two-Pass Architecture Implementation Summary

**Date**: 2025-12-17  
**Status**: ✅ Complete  
**Issue**: Refactor prompt design structure for better reliability and consistency

---

## Problem Statement

The original single-pass approach had three structural problems:

1. **Truncation Risk**: Asking for all 15 scripts (~19,640 words) in one response frequently hit the 32k token limit
2. **Knowledge Cutoff Language**: Model would say "no live browsing" because web search wasn't properly enabled
3. **Inconsistent Facts**: JSON growing across continuations led to different facts in different chapters

---

## Solution: Two-Pass Architecture

### Pass A (gpt-5.2-pro with web search)
**Purpose**: Generate foundation content with web-verified facts

**Generates**:
- `sources[]` - 8-20 web search results with dates
- `canonical_pack` - Compact reference (1k-2.5k words) containing:
  - timeline
  - key_facts
  - key_players
  - claims_evidence
  - beats_outline
  - punchlines
  - historical_context
- `content[L1]` - Long format script (~10,000 words)

**Key Features**:
- Web search tool explicitly enabled for RECENT news
- Uses existing model knowledge for HISTORICAL CONTEXT and deeper analysis
- Combines web search + existing knowledge for richer insights
- Instruction: "Never say you cannot browse"
- Fallback: "sources within the window are limited" if scarce
- Complete JSON output (no continuation logic)

### Pass B (gpt-4.1-nano without web search)
**Purpose**: Generate derivative content from canonical pack

**Generates**:
- `content[M1-M2]` - 2 medium chapters (2,500 words each)
- `content[S1-S4]` - 4 short chapters (1,000 words each)
- `content[R1-R8]` - 8 reel chapters (80 words each)

**Key Features**:
- Uses canonical_pack ONLY (no new facts)
- Beat allocation strategy for content distribution
- Cheaper model (no web search overhead)
- Complete JSON output (no continuation logic)

### Final Merge
Server merges `L1` from Pass A + `M1-M2, S1-S4, R1-R8` from Pass B into single content array.

---

## Benefits

### 1. Avoids Truncation
- Pass A: ~18,500 tokens (L1 + overhead)
- Pass B: ~13,000 tokens (M1-M2, S1-S4, R1-R8)
- Total: ~31,500 tokens split across 2 calls
- Both well within 32,768 token limit

### 2. Proper Web Search + Historical Context
- Pass A uses web_search tool explicitly for RECENT news
- Pass A uses existing model knowledge for HISTORICAL CONTEXT
- No "knowledge cutoff" disclaimers
- Fresh sources verified before writing
- Richer content by combining current events with historical patterns
- Sources and context shared via canonical_pack

### 3. Consistent Facts
- All content pieces use same canonical_pack
- No new facts added in Pass B
- Same events, dates, numbers across all 15 scripts
- Punchlines reused appropriately

### 4. Cost Effective
- Web search only in Pass A (where needed)
- Pass B uses cheaper gpt-4.1-nano model
- No continuation overhead
- Predictable token usage

---

## Implementation Details

### Files Changed

1. **scripts/responses_api_generator.py**
   - Added `PASS_A_INSTRUCTIONS` and `PASS_B_INSTRUCTIONS`
   - Added `CANONICAL_PACK_TEMPLATE`
   - Implemented `generate_pass_a_input()` and `generate_pass_b_input()`
   - Implemented `generate_pass_a_content()` and `generate_pass_b_content()`
   - Implemented `generate_all_content_two_pass()` merge function
   - Updated `generate_all_content_with_responses_api()` to use two-pass

2. **scripts/global_config.py**
   - Added `gpt-4.1-nano` to `OPENAI_MODEL_ENDPOINTS`

3. **scripts/test_two_pass_generation.py** (new)
   - Structure validation tests
   - All tests passing (5/5)

4. **RESPONSES_API_IMPLEMENTATION.md**
   - Updated with two-pass architecture details
   - Added canonical_pack documentation
   - Updated request/response formats

---

## Word Count Targets

| Content | Count | Words Each | Total Words |
|---------|-------|------------|-------------|
| L1      | 1     | 10,000     | 10,000      |
| M1-M2   | 2     | 2,500      | 5,000       |
| S1-S4   | 4     | 1,000      | 4,000       |
| R1-R8   | 8     | 80         | 640         |
| **Total** | **15** | -       | **19,640**  |

---

## Canonical Pack Structure

```json
{
  "timeline": "Chronological events with dates",
  "key_facts": "Core facts for all scripts",
  "key_players": "People, companies, organizations",
  "claims_evidence": "Claims with supporting sources",
  "beats_outline": "10-15 story beats for distribution",
  "punchlines": "Witty lines to reuse",
  "historical_context": "Background info, past precedents, patterns for deeper analysis"
}
```

**Purpose**:
- Ensures consistency across all 15 content pieces
- Provides beat allocation structure
- Tracks evidence for claims
- Enables fact reuse without repetition
- Supplies historical context for richer, more insightful analysis

---

## Beat Allocation Strategy

Pass B distributes beats from canonical_pack:

- **M1**: Beats 1-5
- **M2**: Beats 6-10
- **S1-S4**: 2-3 beats each, sequentially
- **R1-R8**: 1 beat or key fact cluster each

This ensures:
- No beat duplication
- Complete story coverage
- Appropriate depth per format

---

## API Endpoints

Both passes use the same endpoint with different configurations:

**Endpoint**: `POST https://api.openai.com/v1/responses`

**Pass A**:
```python
{
  "model": "gpt-5.2-pro",
  "tools": [{"type": "web_search"}],
  "max_output_tokens": 18500,
  "input": "..." 
}
```

**Pass B**:
```python
{
  "model": "gpt-4.1-nano",
  "tools": None,
  "max_output_tokens": 13000,
  "input": "..."
}
```

---

## Testing

### Structure Tests (Passing)
✅ Pass A input generation  
✅ Pass B input generation  
✅ Instruction template validation  
✅ Canonical pack structure  
✅ Output format expectations  

### Integration Tests (Requires Credentials)
⏳ Full two-pass generation with real API  
⏳ Word count accuracy validation  
⏳ Web search source verification  
⏳ Canonical pack quality assessment  

---

## Migration Notes

### No Breaking Changes
- `generate_all_content_with_responses_api()` signature unchanged
- Returns same data structure (list of content dicts)
- Backward compatible with existing pipeline

### Key Differences
- Now makes 2 API calls instead of attempting 1 huge call
- Uses different models (gpt-5.2-pro + gpt-4.1-nano)
- Adds `canonical_pack` to metadata
- More reliable (no truncation)
- More consistent (shared canonical_pack)

---

## Next Steps

1. **Integration Testing**: Test with real OpenAI credentials
2. **Quality Assessment**: Compare output quality with single-pass
3. **Cost Analysis**: Measure actual API costs for both passes
4. **Performance Monitoring**: Track success rates and timing

---

## References

- **Implementation**: `scripts/responses_api_generator.py`
- **Tests**: `scripts/test_two_pass_generation.py`
- **Documentation**: `RESPONSES_API_IMPLEMENTATION.md`
- **Configuration**: `scripts/global_config.py`

---

**Status**: Implementation complete, ready for integration testing.
