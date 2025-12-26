#!/usr/bin/env python3
"""
Parser for converting script text to structured segments with dialogue.

This module provides functionality to parse script text in HOST_A/HOST_B format
and convert it into structured segments with dialogue arrays suitable for
TTS generation and other downstream processing.
"""
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def parse_script_text_to_segments(script_text: str, default_segment_title: str = "Main Content") -> List[Dict[str, Any]]:
    """
    Parse script text in HOST_A/HOST_B format into structured segments with dialogue.
    
    Args:
        script_text: Script text with HOST_A: ... HOST_B: ... format
        default_segment_title: Default title for segments (default: "Main Content")
        
    Returns:
        List of segment dictionaries with dialogue arrays
        
    Example:
        >>> script_text = "HOST_A: Hello! HOST_B: Hi there! HOST_A: How are you?"
        >>> segments = parse_script_text_to_segments(script_text)
        >>> len(segments)
        1
        >>> len(segments[0]['dialogue'])
        3
    """
    if not script_text or not script_text.strip():
        logger.warning("Empty script text provided to parser")
        return []
    
    # Split by HOST_* markers (supports HOST_A, HOST_B, HOST_C, ...)
    # Pattern matches HOST_X: at the start or after whitespace
    pattern = r'(HOST_[A-Z0-9]+):\s*'
    
    # Find all matches with their positions
    matches = list(re.finditer(pattern, script_text))
    
    if not matches:
        # Fallback: treat as a single-speaker monologue.
        # This is intentional to support 'use_roles=false' or single-role scripts.
        cleaned = script_text.strip()
        if not cleaned:
            return []
        logger.warning(
            f"No HOST_* markers found; treating script as monologue (length: {len(cleaned)})"
        )
        segment = {
            'chapter': 1,
            'title': default_segment_title,
            'start_time': 0,
            'duration': 0,
            'dialogue': [{'speaker': 'A', 'text': cleaned}],
        }
        return [segment]
    
    # Extract dialogue items
    dialogue = []
    for i, match in enumerate(matches):
        speaker = match.group(1)  # e.g., HOST_A, HOST_B, HOST_C
        raw_code = speaker.replace('HOST_', '')
        # Downstream currently supports A/B voices. Map others to A.
        speaker_code = raw_code if raw_code in ('A', 'B') else 'A'
        
        # Get text from end of this match to start of next match (or end of string)
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(script_text)
        text = script_text[start_pos:end_pos].strip()
        
        # Remove common artifacts
        text = text.rstrip()
        
        # Skip empty dialogue
        if not text:
            continue
        
        dialogue.append({
            'speaker': speaker_code,
            'text': text
        })
    
    if not dialogue:
        logger.warning(f"No dialogue extracted from script text with {len(matches)} HOST markers")
        return []
    
    logger.info(f"Parsed {len(dialogue)} dialogue items from script text")
    
    # Create a single segment with all dialogue
    # In the future, we could split into multiple segments based on content or length
    segment = {
        'chapter': 1,
        'title': default_segment_title,
        'start_time': 0,
        'duration': 0,  # Duration will be calculated after TTS generation
        'dialogue': dialogue
    }
    
    return [segment]


def parse_script_text_to_multi_segments(
    script_text: str,
    target_dialogues_per_segment: int = 50
) -> List[Dict[str, Any]]:
    """
    Parse script text into multiple segments by splitting dialogue into chunks.
    
    This is useful for very long scripts where having all dialogue in one segment
    would be unwieldy for processing or display.
    
    Args:
        script_text: Script text with HOST_A: ... HOST_B: ... format
        target_dialogues_per_segment: Target number of dialogue items per segment
        
    Returns:
        List of segment dictionaries with dialogue arrays
    """
    # First, parse all dialogue
    single_segment = parse_script_text_to_segments(script_text, "Content")
    
    if not single_segment or not single_segment[0].get('dialogue'):
        return []
    
    all_dialogue = single_segment[0]['dialogue']
    
    # If dialogue is short enough, return single segment
    if len(all_dialogue) <= target_dialogues_per_segment:
        single_segment[0]['title'] = "Main Content"
        return single_segment
    
    # Split into multiple segments
    segments = []
    num_segments = (len(all_dialogue) + target_dialogues_per_segment - 1) // target_dialogues_per_segment
    
    for i in range(num_segments):
        start_idx = i * target_dialogues_per_segment
        end_idx = min((i + 1) * target_dialogues_per_segment, len(all_dialogue))
        
        segment_dialogue = all_dialogue[start_idx:end_idx]
        
        segment = {
            'chapter': i + 1,
            'title': f"Part {i + 1}",
            'start_time': 0,  # Will be calculated later
            'duration': 0,
            'dialogue': segment_dialogue
        }
        segments.append(segment)
    
    logger.info(f"Split {len(all_dialogue)} dialogue items into {len(segments)} segments")
    
    return segments


def convert_content_script_to_segments(content_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a content item with 'script' field to have 'segments' field.
    
    This function checks if a content item has a 'script' field but no 'segments' field,
    and if so, parses the script text to create structured segments.
    
    Args:
        content_item: Content dictionary that may have 'script' field
        
    Returns:
        Modified content dictionary with 'segments' field added
    """
    # If segments already exist, return as-is
    if 'segments' in content_item and content_item['segments']:
        return content_item
    
    # If no script field, log warning and return with empty segments
    if 'script' not in content_item:
        code = content_item.get('code', 'UNKNOWN')
        logger.warning(f"Content item {code} has neither 'script' nor 'segments' field")
        content_item['segments'] = []
        return content_item
    
    # Parse script text to segments
    script_text = content_item['script']
    code = content_item.get('code', 'UNKNOWN')
    content_type = content_item.get('type', 'unknown')
    
    logger.info(f"Converting script text to segments for {code} ({content_type})")
    
    # Use multi-segment parsing for long-form content
    if content_type == 'long':
        segments = parse_script_text_to_multi_segments(script_text, target_dialogues_per_segment=100)
    else:
        segments = parse_script_text_to_segments(script_text, default_segment_title=content_type.capitalize())
    
    content_item['segments'] = segments
    
    # Log result
    if segments:
        total_dialogue = sum(len(seg.get('dialogue', [])) for seg in segments)
        logger.info(f"  {code}: Created {len(segments)} segment(s) with {total_dialogue} dialogue items")
    else:
        logger.error(f"  {code}: Failed to create any segments from script text!")
    
    return content_item


def validate_segments(segments: List[Dict[str, Any]], content_code: str = "UNKNOWN") -> bool:
    """
    Validate that segments are properly structured and contain dialogue.
    
    Args:
        segments: List of segment dictionaries
        content_code: Code identifier for the content (for logging)
        
    Returns:
        True if segments are valid, False otherwise
    """
    if not segments:
        logger.error(f"{content_code}: No segments found!")
        return False
    
    # Quick check: if all segments have empty dialogue, return early
    total_dialogue = 0
    for i, segment in enumerate(segments):
        if 'dialogue' not in segment:
            logger.error(f"{content_code}: Segment {i+1} missing 'dialogue' field")
            return False
        
        dialogue_items = segment['dialogue']
        if not dialogue_items:
            logger.warning(f"{content_code}: Segment {i+1} has empty dialogue")
            continue
        
        total_dialogue += len(dialogue_items)
        
        # Validate dialogue items
        for j, dialogue_item in enumerate(dialogue_items):
            if 'speaker' not in dialogue_item:
                logger.error(f"{content_code}: Segment {i+1}, dialogue {j+1} missing 'speaker' field")
                return False
            if 'text' not in dialogue_item:
                logger.error(f"{content_code}: Segment {i+1}, dialogue {j+1} missing 'text' field")
                return False
            if not dialogue_item['text'].strip():
                logger.warning(f"{content_code}: Segment {i+1}, dialogue {j+1} has empty text")
    
    if total_dialogue == 0:
        logger.error(f"{content_code}: No dialogue items found across all segments!")
        return False
    
    logger.info(f"{content_code}: Validation passed - {len(segments)} segments with {total_dialogue} dialogue items")
    return True
