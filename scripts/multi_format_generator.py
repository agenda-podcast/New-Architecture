#!/usr/bin/env python3
"""
Multi-format content generation for podcast topics using TWO-PASS architecture.

This module generates multiple scripts using a two-pass approach:
- Pass A (gpt-5.2-pro + web_search): L* (long) scripts
- Pass B (gpt-4.1-nano): M/S/R summaries derived from Pass A output (no new facts)

Default format counts are configured in global_config.py CONTENT_TYPES; per-topic overrides are supported.

Key features:
- TWO-PASS architecture prevents truncation and ensures consistency
- Pass A uses web search for latest news and generates long-form content (L1)
- Pass B derives all other formats from SOURCE_TEXT to ensure consistency and avoid adding new information
- Cost-effective: Web search only in Pass A, cheaper model in Pass B

Implementation details:
- Uses responses_api_generator.py for two-pass generation
- Backwards compatible with existing pipeline
- No continuation logic needed - complete JSON from both passes
"""
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from global_config import CONTENT_TYPES

# Try to import two-pass generator
try:
    from responses_api_generator import generate_all_content_two_pass
    TWO_PASS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Two-pass generator not available: {e}")
    TWO_PASS_AVAILABLE = False
    generate_all_content_two_pass = None

# Global variable to track if generation is already in progress (prevents duplicate calls)
# Note: This is not thread-safe. If multi-threaded execution is needed in the future,
# replace with threading.Lock() for proper synchronization.
_generation_in_progress = False


def get_enabled_content_types(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get list of enabled content types with their specifications.
    
    Parses the topic configuration to determine which content types are enabled
    and generates a complete specification list for each piece of content.
    
    Args:
        config: Topic configuration dictionary containing 'content_types' with
               boolean flags for 'long', 'medium', 'short', 'reels'
    
    Returns:
        List of dictionaries, each containing:
        - type: Content type name ('long', 'medium', 'short', 'reels')
        - index: 1-based index within type
        - code: Content code (e.g., 'L1', 'M2', 'S3', 'R4')
        - target_words: Target word count for this content type
    
    Example:
        >>> config = {'content_types': {'long': True, 'medium': True}}
        >>> specs = get_enabled_content_types(config)
        >>> len(specs)  # 1 long + 2 medium = 3
        3
        >>> specs[0]['code']
        'L1'
    """
    enabled = []
    content_types_config = config.get('content_types', {})

    for type_name, type_spec in CONTENT_TYPES.items():
        raw = content_types_config.get(type_name, False)

        if isinstance(raw, bool):
            is_enabled = raw
            items = type_spec['count']
            max_words = type_spec['target_words']
        elif isinstance(raw, dict):
            is_enabled = bool(raw.get('enabled', False))
            items = int(raw.get('items', type_spec['count']))
            max_words = int(raw.get('max_words', type_spec['target_words']))
        else:
            # Invalid config shape; treat as disabled.
            is_enabled = False
            items = 0
            max_words = type_spec['target_words']

        if not is_enabled or items <= 0:
            continue

        for i in range(items):
            enabled.append({
                'type': type_name,
                'index': i + 1,
                'code': f"{type_spec['code_prefix']}{i + 1}",
                'target_words': max_words,
            })
    
    return enabled


def generate_multi_format_scripts(config: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate multiple format scripts using TWO-PASS architecture with Responses API.
    
    Pass A (gpt-5.2-pro + web_search): L* scripts
    Pass B (gpt-4.1-nano, no web_search): M/S/R summaries from SOURCE_TEXT
    
    This approach:
    - Avoids truncation by splitting into two manageable requests
    - Uses web search only in Pass A (cost effective)
    - Ensures consistency by deriving M/S/R strictly from SOURCE_TEXT (no new facts)
    - Generates all content as standalone pieces
    
    IMPORTANT: This function should be called ONCE per topic, not once per content type.
    It generates ALL enabled content types using two-pass architecture.
    """
    global _generation_in_progress
    
    # Check if generation is already in progress (prevent duplicate calls)
    if _generation_in_progress:
        logger.error("="*80)
        logger.error("ERROR: generate_multi_format_scripts called while generation already in progress!")
        logger.error("This indicates a bug - the function should only be called once per topic.")
        logger.error("="*80)
        raise RuntimeError("Duplicate call detected: generate_multi_format_scripts is already in progress. "
                         "This function should only be called once per topic to avoid wasting API quota.")
    
    try:
        _generation_in_progress = True
        
        # Check if two-pass generator is available
        if not TWO_PASS_AVAILABLE or generate_all_content_two_pass is None:
            raise ImportError(
                "Two-pass generator (responses_api_generator.py) is not available. "
                "This may be due to missing dependencies like the openai package. "
                "Please ensure all dependencies are installed."
            )
        
        # Get enabled content types from config
        content_specs = get_enabled_content_types(config)
        if not content_specs:
            raise ValueError("No content types enabled in configuration. Please enable at least one content type in topic config.")
        
        # Log what we're about to generate
        logger.info("="*80)
        logger.info("MULTI-FORMAT GENERATION - TWO-PASS ARCHITECTURE")
        logger.info("="*80)
        logger.info(f"Topic: {config.get('title', 'Unknown')}")
        logger.info(f"Enabled content types from config: {config.get('content_types', {})}")
        logger.info(f"Scripts to generate: {len(content_specs)}")
        logger.info(f"Script codes: {[s['code'] for s in content_specs]}")
        if sources:
            logger.info(f"Note: {len(sources)} sources provided but will not be used (two-pass uses web_search)")
        logger.info("="*80)
        
        print(f"\n{'='*60}")
        print(f"TWO-PASS ARCHITECTURE (Pass A + Pass B)")
        print(f"{'='*60}")
        print(f"Topic: {config.get('title', 'Unknown')}")
        print(f"Generating {len(content_specs)} scripts using two passes: {[s['code'] for s in content_specs]}")
        enabled_types = sorted({s['type'] for s in content_specs})
        print(f"Content types enabled: {', '.join(enabled_types)}")
        print(f"Pass A (gpt-5.2-pro + web_search): canonical pack + optional long SOURCE_TEXT")
        print(f"Pass B (gpt-5-nano by default): structured M/S/R scripts from CANONICAL_PACK")
        if sources:
            print(f"Note: {len(sources)} pre-collected sources ignored (two-pass uses web_search)")
        print(f"{'='*60}\n")
        
        # Two-pass generation (function now accepts config-only call style)
        two_pass_data = generate_all_content_two_pass(config, sources=sources)

        # Normalized output
        content_list = two_pass_data.get('content', []) if isinstance(two_pass_data, dict) else (two_pass_data or [])
        parsed_data = two_pass_data if isinstance(two_pass_data, dict) else {"content": content_list}
        
        # Validate that we got all expected scripts
        received_count = len(content_list)
        if received_count != len(content_specs):
            logger.warning(f"Expected {len(content_specs)} scripts but received {received_count}")
            print(f"WARNING: Expected {len(content_specs)} scripts but received {received_count}")
        else:
            logger.info(f"Successfully received all {received_count} scripts")
            print(f"✓ Successfully generated all {received_count} scripts using two-pass architecture")
        
        return parsed_data
        
    except Exception as e:
        print(f"Error during generation: {e}")
        logger.error(f"Exception during generation: {e}", exc_info=True)
        raise
    
    finally:
        # Always reset the flag when done
        _generation_in_progress = False
