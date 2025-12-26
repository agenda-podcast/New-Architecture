#!/usr/bin/env python3
"""Generate podcast script from sources."""
import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from config import load_topic_config, get_data_dir, get_output_dir

# OpenAI for ChatGPT API
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# OpenAI utilities for dynamic endpoint selection
try:
    from openai_utils import create_openai_completion, extract_completion_text, get_finish_reason
except ImportError:
    create_openai_completion = None
    extract_completion_text = None
    get_finish_reason = None

# Multi-format generator
try:
    from multi_format_generator import generate_multi_format_scripts, get_enabled_content_types
except ImportError:
    generate_multi_format_scripts = None
    get_enabled_content_types = None

# Script parser for converting script text to segments
try:
    from script_parser import convert_content_script_to_segments, validate_segments
except ImportError:
    convert_content_script_to_segments = None
    validate_segments = None

# Constants
MAX_COMPLETION_TOKENS = 125000  # Maximum tokens for ChatGPT response
MAX_ERROR_OUTPUT_LENGTH = 500  # Maximum length of error output to display


# Source validation function removed in architecture v2
# OpenAI's web_search tool handles source discovery and validation internally


def generate_script_with_chatgpt(config: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate script using ChatGPT API.
    
    Uses gpt-5-mini model for conversational analysis with chunked response handling
    for long scripts.
    """
    # Get API key from environment
    api_key = os.environ.get('GPT_KEY') or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("GPT_KEY or OPENAI_API_KEY environment variable is required")
    
    if OpenAI is None:
        raise ImportError("openai package is required. Install with: pip install openai")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Prepare sources for the prompt
    # NOTE: In architecture v2, sources come from OpenAI's web_search tool
    # This function is deprecated in favor of responses_api_generator.py
    sources_text_parts = []
    
    for i, source in enumerate(sources[:20]):  # Limit to 20 sources to avoid token limits
        source_text = f"Source {i+1}:\n"
        source_text += f"Title: {source.get('title', 'N/A')}\n"
        source_text += f"URL: {source.get('url', 'N/A')}\n"
        source_text += f"Date: {source.get('date', 'N/A')}\n"
        source_text += f"Description: {source.get('description', 'N/A')}\n"
        
        sources_text_parts.append(source_text)
    
    sources_text = "\n\n".join(sources_text_parts)
    
    # Get host information
    voice_a_name = config.get('voice_a_name', 'Host A')
    voice_a_bio = config.get('voice_a_bio', 'Expert host')
    voice_b_name = config.get('voice_b_name', 'Host B')
    voice_b_bio = config.get('voice_b_bio', 'Expert host')
    
    # Get custom GPT prompt and script length setting
    custom_prompt = config.get('gpt_prompt', '')
    script_length = config.get('script_length', 'long')  # short, medium, long
    
    # Determine target duration based on script length
    if script_length == 'short':
        target_duration = 900  # 15 minutes
        duration_desc = "15 minutes"
    elif script_length == 'medium':
        target_duration = 1350  # 22.5 minutes
        duration_desc = "20-25 minutes"
    else:  # long
        target_duration = 1800  # 30 minutes
        duration_desc = "30 minutes"
    
    # Construct the prompt for deep conversational analysis
    prompt = f"""You are creating a conversational deep dive podcast script for: {config['title']}

Topic Description: {config.get('description', '')}

HOSTS:
- Host A ({voice_a_name}): {voice_a_bio}
- Host B ({voice_b_name}): {voice_b_bio}

CUSTOM GUIDANCE:
{custom_prompt}

Your task is to create an engaging, informative {duration_desc} (~{target_duration} seconds) conversational dialogue that deeply analyzes the following fresh sources. Use your deep thinking capability to provide insightful analysis, connections between topics, and thought-provoking discussion.

The hosts should speak in character based on their backgrounds and expertise. {voice_a_name} and {voice_b_name} should have natural, flowing conversations that showcase their knowledge and perspectives.

SOURCES:
{sources_text}{url_instruction}

REQUIREMENTS:
1. Create a natural, flowing conversation between {voice_a_name} (speaker A) and {voice_b_name} (speaker B)
2. Target duration: approximately {duration_desc} ({target_duration} seconds) of dialogue
3. Divide into 4-6 segments/chapters with clear themes or topics
4. Include:
   - Deep analysis and discussion of key points from sources
   - Connections between different sources and ideas
   - Expert insights and critical thinking reflecting the hosts' expertise
   - Engaging back-and-forth dialogue (not just one host lecturing)
   - Discussion that stays in character with host backgrounds

6. Make the dialogue:
   - Conversational and natural (like a real podcast)
   - Informative but accessible
   - Analytical and thought-provoking
   - Well-paced with good flow between topics
   - Appropriate to each host's expertise and background

OUTPUT FORMAT (JSON):
{{
  "segments": [
    {{
      "chapter": 1,
      "title": "Segment title",
      "start_time": 0,
      "duration": estimated_seconds,
      "dialogue": [
        {{"speaker": "A", "text": "dialogue text"}},
        {{"speaker": "B", "text": "dialogue text"}},
        ...
      ]
    }},
    ...
  ]
}}

IMPORTANT: If your response is too long and gets cut off, structure it so that you can provide the JSON in multiple parts. End with a clear indication if more content follows. The system will send "Next" to request continuation."""
    
    print(f"Calling ChatGPT API (model: gpt-5-mini) for script generation...")
    print(f"Script length: {script_length} (target: {duration_desc})")
    print(f"Using {len(sources)} sources for context")
    
    try:
        # Collect response chunks
        messages = [{"role": "user", "content": prompt}]
        all_responses = []
        continuation_count = 0
        max_continuations = 5  # Limit to prevent infinite loops
        
        while continuation_count < max_continuations:
            # Use gpt-5-mini model with dynamic endpoint selection
            model = "gpt-5-mini"
            response = create_openai_completion(
                client=client,
                model=model,
                messages=messages,
                json_mode=True,
                max_completion_tokens=MAX_COMPLETION_TOKENS
            )
            
            # Extract the response using endpoint-aware helper
            response_text = extract_completion_text(response, model)
            all_responses.append(response_text)
            
            print(f"Received response chunk {continuation_count + 1} ({len(response_text)} chars)")
            
            # Check if response indicates continuation needed
            # Multiple detection methods:
            # 1. String markers indicating truncation
            response_lower = response_text.lower()
            has_continuation_marker = any(marker in response_lower for marker in [
                'continued', 'to be continued', '(continued)', 'more content follows',
                'response continues', 'part 1 of', 'part 2 of', 'truncated'
            ])
            
            # 2. Check for incomplete JSON structure
            has_incomplete_json = (
                response_text.count('{') != response_text.count('}') or
                response_text.count('[') != response_text.count(']') or
                not response_text.strip().endswith(('}', ']'))
            )
            
            # 3. Check finish reason from API (endpoint-aware)
            finish_reason = get_finish_reason(response, model)
            was_length_limited = finish_reason == 'length'
            
            needs_continuation = has_continuation_marker or has_incomplete_json or was_length_limited
            
            if needs_continuation:
                continuation_count += 1
                print(f"Response needs continuation (marker: {has_continuation_marker}, incomplete: {has_incomplete_json}, length: {was_length_limited})")
                print(f"Requesting more (attempt {continuation_count}/{max_continuations})...")
                
                # Add assistant's response and user's continuation request
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": "Next"})
            else:
                # Response appears complete
                break
        
        # Merge all response chunks with smart handling
        if len(all_responses) == 1:
            full_response = all_responses[0]
        else:
            # Try to merge intelligently
            merged = all_responses[0]
            for i in range(1, len(all_responses)):
                chunk = all_responses[i]
                # Remove markdown artifacts at boundaries
                chunk = chunk.strip()
                if chunk.startswith('```'):
                    chunk = chunk.split('\n', 1)[1] if '\n' in chunk else chunk
                # Append with minimal separator
                merged += '\n' + chunk
            full_response = merged
        
        print(f"Total response length: {len(full_response)} chars across {len(all_responses)} chunks")
        
        # Parse the JSON response
        response_text = full_response.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON with detailed error handling
        try:
            script_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            # Provide context about parsing error
            error_context = response_text[:MAX_ERROR_OUTPUT_LENGTH]
            if len(response_text) > MAX_ERROR_OUTPUT_LENGTH:
                error_context += "... (truncated)"
            raise ValueError(
                f"Failed to parse ChatGPT response as JSON at position {e.pos}: {e.msg}\n"
                f"Response preview: {error_context}"
            ) from e
        
        # Validate and ensure proper structure
        if 'segments' not in script_data:
            raise ValueError("Response missing 'segments' field")
        
        # Calculate actual total duration
        total_duration = sum(seg.get('duration', 0) for seg in script_data['segments'])
        
        # Build final script structure
        result = {
            'title': config['title'],
            'duration_sec': total_duration,
            'segments': script_data['segments'],
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'model': 'gpt-5-mini',
                'num_sources': len(sources),
                'api_provider': 'openai'
            }
        }
        
        print(f"Script generated successfully: {len(result['segments'])} segments, ~{total_duration} seconds")
        return result
        
    except ValueError as e:
        # ValueError is raised by our JSON parsing with context - re-raise with message
        print(f"Error: {e}")
        raise
    except Exception as e:
        print(f"Error calling ChatGPT API: {e}")
        raise


def generate_script_with_llm(config: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate script using LLM.
    
    Requires GPT_KEY to be set. Raises an exception if not available.
    """
    # Check if GPT_KEY is available
    if not (os.environ.get('GPT_KEY') or os.environ.get('OPENAI_API_KEY')):
        raise Exception(
            "GPT_KEY or OPENAI_API_KEY environment variable not set. "
            "Script generation requires OpenAI API access. "
            "Please set GPT_KEY in your environment or GitHub secrets."
        )
    
    try:
        return generate_script_with_chatgpt(config, sources)
    except Exception as e:
        print(f"ERROR: ChatGPT API failed: {e}")
        raise Exception(
            f"Failed to generate script using ChatGPT API: {e}. "
            "Please check your API key and quota limits."
        )


def script_to_text(script: Dict[str, Any], config: Dict[str, Any] = None) -> str:
    """Convert script structure to readable text format with voice names."""
    lines = []
    lines.append(f"# {script['title']}")
    lines.append(f"Duration: {script['duration_sec']} seconds")
    lines.append("")
    
    # Add voice information if config provided
    if config:
        voice_a_name = config.get('voice_a_name', 'A')
        voice_b_name = config.get('voice_b_name', 'B')
        lines.append("## Hosts")
        lines.append(f"- **{voice_a_name}** ({config.get('voice_a_gender', 'Unknown')}): {config.get('voice_a_bio', 'Host A')}")
        lines.append(f"- **{voice_b_name}** ({config.get('voice_b_gender', 'Unknown')}): {config.get('voice_b_bio', 'Host B')}")
        lines.append("")
    else:
        voice_a_name = 'A'
        voice_b_name = 'B'
    
    for segment in script['segments']:
        lines.append(f"## Chapter {segment['chapter']}: {segment['title']}")
        lines.append(f"Time: {segment.get('start_time', 0)}s")
        lines.append("")
        
        for dialogue in segment['dialogue']:
            speaker_code = dialogue['speaker']
            speaker_name = voice_a_name if speaker_code == 'A' else voice_b_name
            lines.append(f"**{speaker_name}**: {dialogue['text']}")
            lines.append("")
    
    return '\n'.join(lines)


def generate_chapters(script: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate chapter markers from script.
    
    Uses .get() with defaults to handle segments that may have missing fields,
    making the function more defensive against malformed script data.
    """
    chapters = []
    for segment in script['segments']:
        chapters.append({
            'title': segment.get('title', 'Untitled'),
            'start_time': segment.get('start_time', 0)
        })
    return chapters


def chapters_to_ffmeta(chapters: List[Dict[str, Any]]) -> str:
    """Convert chapters to FFmpeg metadata format."""
    lines = [';FFMETADATA1']
    
    for i, chapter in enumerate(chapters):
        start_ms = chapter['start_time'] * 1000
        # End is start of next chapter or very long duration
        if i < len(chapters) - 1:
            end_ms = chapters[i + 1]['start_time'] * 1000
        else:
            end_ms = start_ms + 3600000  # 1 hour
        
        lines.append('[CHAPTER]')
        lines.append('TIMEBASE=1/1000')
        lines.append(f'START={start_ms}')
        lines.append(f'END={end_ms}')
        lines.append(f'title={chapter["title"]}')
    
    return '\n'.join(lines)


# DEPRECATED: RSS generation removed per project requirements
# This function is kept for backwards compatibility but should not be used
def script_to_rss_description(script: Dict[str, Any], config: Dict[str, Any] = None) -> str:
    """
    DEPRECATED: Convert script to RSS-compatible HTML description.
    RSS generation has been removed from the project.
    This function is kept for backwards compatibility only.
    """
    lines = []
    lines.append(f"<h2>{script['title']}</h2>")
    lines.append(f"<p><strong>Duration:</strong> {script['duration_sec'] // 60} minutes</p>")
    
    # Add host information
    if config:
        voice_a_name = config.get('voice_a_name', 'Host A')
        voice_b_name = config.get('voice_b_name', 'Host B')
        lines.append("<h3>Your Hosts</h3>")
        lines.append("<ul>")
        lines.append(f"<li><strong>{voice_a_name}</strong> ({config.get('voice_a_gender', '')}): {config.get('voice_a_bio', '')}</li>")
        lines.append(f"<li><strong>{voice_b_name}</strong> ({config.get('voice_b_gender', '')}): {config.get('voice_b_bio', '')}</li>")
        lines.append("</ul>")
    else:
        voice_a_name = 'Host A'
        voice_b_name = 'Host B'
    
    lines.append("<h3>Episode Segments</h3>")
    lines.append("<ol>")
    for segment in script['segments']:
        lines.append(f"<li><strong>{segment.get('title', 'Untitled')}</strong> ({segment.get('start_time', 0)}s)</li>")
    lines.append("</ol>")
    
    lines.append("<h3>Full Transcript</h3>")
    for segment in script['segments']:
        lines.append(f"<h4>Chapter {segment['chapter']}: {segment['title']}</h4>")
        lines.append("<p>")
        
        for dialogue in segment['dialogue']:
            speaker_code = dialogue.get('speaker', 'A')
            # Validate speaker code
            if speaker_code not in ['A', 'B']:
                speaker_code = 'A'
            speaker_name = voice_a_name if speaker_code == 'A' else voice_b_name
            # Escape HTML characters in dialogue text
            text = dialogue.get('text', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            lines.append(f"<strong>{speaker_name}:</strong> {text}<br/>")
        
        lines.append("</p>")
    
    return '\n'.join(lines)


def generate_for_topic(topic_id: str, date_str: str = None) -> bool:
    """
    Generate script(s) for a single topic using multi-format generation.
    
    Note: Single-format generation has been removed. Topics must have the
    'content_types' field configured in their topic configuration to specify
    which formats to generate (long, medium, short, reels).
    
    Args:
        topic_id: Topic identifier (e.g., 'topic-01')
        date_str: Date string in YYYYMMDD format (default: today)
        
    Returns:
        True if all scripts generated successfully, False otherwise
    """
    try:
        if date_str is None:
            date_str = datetime.now().strftime('%Y%m%d')
        
        config = load_topic_config(topic_id)
        data_dir = get_data_dir(topic_id)
        output_dir = get_output_dir(topic_id)
        
        # Always use multi-format generation based on content_types configuration
        return generate_multi_format_for_topic(topic_id, date_str, config, data_dir, output_dir)
    
    except Exception as e:
        print(f"Error generating scripts for {topic_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_multi_format_for_topic(topic_id: str, date_str: str, config: Dict[str, Any],
                                    data_dir: Path, output_dir: Path) -> bool:
    """Generate multiple format scripts for a topic (15 scripts with different durations).
    
    Note: This function has been updated to work without pre-collected source data.
    Script generation now relies solely on OpenAI Responses API with web search capabilities.
    """
    try:
        if generate_multi_format_scripts is None:
            print("Error: multi_format_generator not available")
            return False
        
        # No longer load sources from data files - use topic instructions directly
        # The OpenAI Responses API will fetch and analyze content via web search
        print(f"Generating scripts for {topic_id} using topic instructions and OpenAI Responses API...")
        
        # Use empty source list - script generation will rely on OpenAI web search
        picked_sources = []
        
        # Note: Source collection, validation, and article fetching are no longer needed
        # The OpenAI Responses API handles web search and content analysis directly
        
        # Generate all scripts using multi-format generator with topic config only
        print(f"Generating multi-format scripts for {topic_id}...")
        # Pass empty sources list - generator will use topic instructions and OpenAI web search
        multi_data = generate_multi_format_scripts(config, picked_sources)
        
        # Process each content piece
        content_list = multi_data.get('content', [])
        if not content_list:
            print("Error: No content generated")
            return False
        
        print(f"Generated {len(content_list)} content pieces")
        
        # Save each script
        for content_item in content_list:
            code = content_item.get('code', 'UNKNOWN')
            content_type = content_item.get('type', 'unknown')
            target_duration = content_item.get('target_duration', 0)
            
            # Convert script text to segments if needed
            if convert_content_script_to_segments is not None:
                content_item = convert_content_script_to_segments(content_item)
            else:
                print(f"Warning: script_parser not available, segments may be missing")
            
            segments = content_item.get('segments', [])
            
            # Validate segments before proceeding
            if not segments:
                print(f"ERROR: {code} has no segments! This will cause TTS generation to fail.")
                print(f"  Content type: {content_type}")
                print(f"  Has 'script' field: {'script' in content_item}")
                if 'script' in content_item:
                    script_preview = content_item['script'][:200] if content_item['script'] else "(empty)"
                    print(f"  Script preview: {script_preview}...")
                continue  # Skip this content item
            
            # Validate dialogue in segments
            if validate_segments is not None:
                if not validate_segments(segments, code):
                    print(f"ERROR: {code} has invalid segments! Skipping.")
                    continue
            
            total_dialogue = sum(len(seg.get('dialogue', [])) for seg in segments)
            print(f"  {code}: {len(segments)} segment(s), {total_dialogue} dialogue items")
            
            # Build script structure
            script = {
                'title': f"{config['title']} - {code}",
                'duration_sec': target_duration,
                'segments': segments,
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'model': 'gpt-5-mini',
                    'num_sources': len(picked_sources),
                    'content_type': content_type,
                    'content_code': code
                }
            }
            
            # Add intro/outro if this is a longer format
            if content_type in ['long', 'medium']:
                if config.get('voice_a_intro') or config.get('voice_b_intro'):
                    intro_dialogue = []
                    if config.get('voice_a_intro'):
                        intro_dialogue.append({'speaker': 'A', 'text': config['voice_a_intro']})
                    if config.get('voice_b_intro'):
                        intro_dialogue.append({'speaker': 'B', 'text': config['voice_b_intro']})
                    
                    intro_segment = {
                        'chapter': 0,
                        'title': 'Introduction',
                        'start_time': 0,
                        'duration': 30,
                        'dialogue': intro_dialogue
                    }
                    script['segments'].insert(0, intro_segment)
                
                if config.get('voice_a_outro') or config.get('voice_b_outro'):
                    outro_dialogue = []
                    if config.get('voice_a_outro'):
                        outro_dialogue.append({'speaker': 'A', 'text': config['voice_a_outro']})
                    if config.get('voice_b_outro'):
                        outro_dialogue.append({'speaker': 'B', 'text': config['voice_b_outro']})
                    
                    # Calculate outro start time - use target_duration from script or sum segments
                    if script['segments']:
                        # Try to use the last segment's timing
                        last_segment = script['segments'][-1]
                        outro_start = last_segment.get('start_time', 0) + last_segment.get('duration', 0)
                        # If segment timing is incomplete, fall back to target duration
                        if outro_start == 0:
                            outro_start = target_duration
                    else:
                        # No segments, use target duration as fallback
                        outro_start = target_duration
                    
                    outro_segment = {
                        'chapter': len(script['segments']) + 1,
                        'title': 'Closing',
                        'start_time': outro_start,
                        'duration': 20,
                        'dialogue': outro_dialogue
                    }
                    script['segments'].append(outro_segment)
            
            # File naming: topic-ID-date-CODE (e.g., topic-01-20241216-L1)
            base_name = f"{topic_id}-{date_str}-{code}"
            
            # Save script text
            script_text = script_to_text(script, config)
            script_path = output_dir / f"{base_name}.script.txt"
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_text)
            
            # Save script JSON
            script_json_path = output_dir / f"{base_name}.script.json"
            with open(script_json_path, 'w', encoding='utf-8') as f:
                json.dump(script, f, indent=2, ensure_ascii=False)
            
            # Save chapters
            chapters = generate_chapters(script)
            chapters_path = output_dir / f"{base_name}.chapters.json"
            with open(chapters_path, 'w', encoding='utf-8') as f:
                json.dump(chapters, f, indent=2, ensure_ascii=False)
            
            # Save FFmpeg metadata
            ffmeta = chapters_to_ffmeta(chapters)
            ffmeta_path = output_dir / f"{base_name}.ffmeta"
            with open(ffmeta_path, 'w', encoding='utf-8') as f:
                f.write(ffmeta)
            
            print(f"  - Saved {code}: {len(segments)} segments, ~{target_duration}s")
        
        # Save sources metadata (empty for new workflow)
        # Note: Sources are no longer pre-collected; OpenAI handles content directly
        sources_meta = {
            'note': 'Sources are now obtained dynamically via OpenAI Responses API web search',
            'topic_queries': config.get('queries', []),
            'generated_at': datetime.now().isoformat()
        }
        sources_path = output_dir / f"{topic_id}-{date_str}.sources.json"
        with open(sources_path, 'w', encoding='utf-8') as f:
            json.dump(sources_meta, f, indent=2, ensure_ascii=False)
        
        print(f"Multi-format scripts generated for {topic_id}: {len(content_list)} pieces")
        
        # Note: RSS feed generation removed per project requirements
        
        return True
        
    except Exception as e:
        print(f"Error generating multi-format scripts for {topic_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Generate podcast script')
    parser.add_argument('--topic', required=True, help='Topic ID')
    parser.add_argument('--date', help='Date string (YYYYMMDD)')
    args = parser.parse_args()
    
    success = generate_for_topic(args.topic, args.date)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
