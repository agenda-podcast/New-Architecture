# Mock Data Improvements

## Overview
This document tracks improvements made to mock response data to ensure test data quality and completeness.

## Validation Framework

### New Tools
1. **`validate_mock_data.py`** - Validates that mock response data word counts match target specifications
   - Analyzes both `pass_a_response.json` and `pass_b_response.json`
   - Reports word count vs target for each content type
   - Identifies content pieces that need expansion or contraction

2. **`expand_mock_data.py`** - Automated script to expand mock data to match targets
   - Generates natural-sounding podcast dialogue
   - Maintains conversational style and topic coherence
   - Updates `actual_words` field to reflect true word count

## Progress Summary

### Pass A Response (L1 - Long-form content)
- **Target:** 10,000 words
- **Original:** 850 words (8.5% of target)
- **Current:** 5,261 words (52.6% of target)
- **Improvement:** 6.2x expansion, significantly more comprehensive and realistic
- **Status:** ✗ NEEDS_FIX (further expansion needed to reach 90-110% of target)

### Pass B Response

#### M1 (Medium-form #1)
- **Target:** 2,500 words
- **Original:** 420 words (16.8% of target)
- **Current:** 1,873 words (74.9% of target)
- **Improvement:** 4.5x expansion
- **Status:** ✗ NEEDS_FIX (close to target, needs ~600 more words)

#### M2 (Medium-form #2)
- **Target:** 2,500 words
- **Original:** 380 words (15.2% of target)
- **Current:** 380 words (15.2% of target)
- **Status:** ✗ NEEDS_FIX (needs expansion)

#### S1-S4 (Short-form content)
- **Target:** 1,000 words each
- **Original:** ~165-180 words each (16.5-18.0% of target)
- **Current:** ~165-180 words each
- **Status:** ✗ NEEDS_FIX (needs expansion)

#### R1-R8 (Reels/social media clips)
- **Target:** 80 words each
- **Original:** ~42-50 words each (52.5-62.5% of target)
- **Current:** ~42-50 words each
- **Status:** ✗ NEEDS_FIX (needs modest expansion, ~30-40 more words each)

## Content Quality Guidelines

All mock data should:
1. **Match Target Word Counts:** Content should be within ±10% of target (e.g., L1 should be 9,000-11,000 words)
2. **Sound Natural:** Dialogue should be conversational and realistic, matching actual podcast style
3. **Be Substantive:** Avoid filler; provide meaningful, topical content
4. **Maintain Coherence:** Each piece should have clear structure and flow
5. **Use Realistic Personas:** Hosts should have distinct voices and conversational patterns

## Validation Process

### Running Validation
```bash
cd scripts
python validate_mock_data.py
```

### Expected Output
- Table showing each content piece with code, type, target, actual word count, percentage, and status
- Summary of how many pieces are OK vs need fixing
- Exit code 0 if all OK, 1 if any need fixing

### Acceptance Criteria
Content passes validation if:
- Actual word count is 90-110% of target word count
- Script is natural-sounding and substantive
- actual_words field matches computed word count

## Automated Expansion

### Running Expansion Script
```bash
cd scripts
python expand_mock_data.py
```

### What It Does
1. Generates comprehensive, natural-sounding dialogue
2. Updates JSON files with new scripts
3. Updates `actual_words` fields
4. Reports progress

### Customization
To add generators for additional content types, edit `expand_mock_data.py` and add functions like:
```python
def generate_m2_script() -> str:
    """Generate expanded M2 (medium-form) script (~2,500 words)."""
    script = """..."""
    return script
```

## Next Steps

### Remaining Work
1. **L1 Expansion:** Add ~4,700 more words to reach 10,000-word target
2. **M1 Expansion:** Add ~600 more words to reach 2,500-word target  
3. **M2 Expansion:** Expand from 380 to ~2,500 words
4. **S1-S4 Expansion:** Expand each from ~180 to ~1,000 words
5. **R1-R8 Expansion:** Expand each from ~45 to ~80 words

### Priority
- **High:** L1, M1, M2 (core long and medium-form content)
- **Medium:** S1-S4 (short-form content)
- **Low:** R1-R8 (already at 50-60% of target, modest expansion needed)

### Approach
1. Use `expand_mock_data.py` as template
2. Add generator functions for each remaining content type
3. Ensure dialogue is natural and topic-appropriate
4. Run validation after each update
5. Iterate until all content passes validation

## Testing Integration

### CI/CD Integration (Future)
Consider adding validation to CI/CD pipeline:
```yaml
- name: Validate Mock Data
  run: |
    cd scripts
    python validate_mock_data.py
```

This ensures mock data quality is maintained during development.

## Benefits of Improved Mock Data

1. **Better Testing:** More realistic test data leads to better test coverage
2. **Accurate Performance:** Understanding system behavior with realistic data sizes
3. **Development Confidence:** Developers can test with data that matches production characteristics
4. **Documentation:** Well-structured mock data serves as examples and documentation

## Related Files

- `test_data/mock_responses/pass_a_response.json` - Long-form (L1) mock data
- `test_data/mock_responses/pass_b_response.json` - Medium, short, and reels (M, S, R) mock data
- `scripts/validate_mock_data.py` - Validation script
- `scripts/expand_mock_data.py` - Expansion script
- `scripts/global_config.py` - Content type specifications (CONTENT_TYPES)

## Version History

### v1.0 (2024-12-18)
- Created validation framework
- Expanded L1 from 850 to 5,261 words
- Expanded M1 from 420 to 1,873 words
- Documented process and next steps
