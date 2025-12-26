#!/usr/bin/env python3
"""
Validate script JSON files for completeness and correctness.

This script checks that all script.json files have the required structure
and content for TTS generation to succeed.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple


def validate_script_structure(script_data: Dict[str, Any], filepath: Path) -> Tuple[bool, List[str]]:
    """
    Validate that a script JSON has the required structure.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check top-level structure
    if not isinstance(script_data, dict):
        errors.append("Script must be a JSON object")
        return False, errors
    
    # Check for required top-level keys
    if 'segments' not in script_data:
        errors.append("Missing required key: 'segments'")
        return False, errors
    
    segments = script_data['segments']
    if not isinstance(segments, list):
        errors.append("'segments' must be a list")
        return False, errors
    
    if len(segments) == 0:
        errors.append("'segments' list is empty - no content to generate")
        return False, errors
    
    # Validate each segment
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict):
            errors.append(f"Segment {i} is not a JSON object")
            continue
        
        # Check for required segment keys
        if 'dialogue' not in segment:
            errors.append(f"Segment {i} missing required key: 'dialogue'")
            continue
        
        dialogue = segment['dialogue']
        if not isinstance(dialogue, list):
            errors.append(f"Segment {i} 'dialogue' must be a list")
            continue
        
        if len(dialogue) == 0:
            errors.append(f"Segment {i} 'dialogue' list is empty")
            continue
        
        # Validate each dialogue chunk
        for j, chunk in enumerate(dialogue):
            if not isinstance(chunk, dict):
                errors.append(f"Segment {i}, dialogue {j} is not a JSON object")
                continue
            
            # Check for required dialogue keys
            if 'speaker' not in chunk:
                errors.append(f"Segment {i}, dialogue {j} missing 'speaker'")
            
            if 'text' not in chunk:
                errors.append(f"Segment {i}, dialogue {j} missing 'text'")
            elif not isinstance(chunk['text'], str):
                errors.append(f"Segment {i}, dialogue {j} 'text' must be a string")
            elif len(chunk['text'].strip()) == 0:
                errors.append(f"Segment {i}, dialogue {j} has empty text")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_script_content(script_data: Dict[str, Any], filepath: Path) -> Tuple[bool, List[str]]:
    """
    Validate content quality of a script JSON.
    
    Returns:
        Tuple of (is_valid, warning_messages)
    """
    warnings = []
    
    # Count total dialogue chunks
    total_chunks = 0
    total_words = 0
    speakers = set()
    
    for segment in script_data.get('segments', []):
        for chunk in segment.get('dialogue', []):
            total_chunks += 1
            text = chunk.get('text', '')
            total_words += len(text.split())
            speakers.add(chunk.get('speaker', 'UNKNOWN'))
    
    # Check for content issues
    if total_chunks < 5:
        warnings.append(f"Very few dialogue chunks ({total_chunks}) - may be incomplete")
    
    if total_words < 50:
        warnings.append(f"Very few words ({total_words}) - script may be too short")
    
    if len(speakers) < 2:
        warnings.append(f"Only {len(speakers)} speaker(s) found - expected dialogue between two hosts")
    
    if 'UNKNOWN' in speakers:
        warnings.append("Some dialogue chunks have missing or invalid speaker identifiers")
    
    return len(warnings) == 0, warnings


def validate_script_file(filepath: Path) -> Tuple[bool, List[str], List[str]]:
    """
    Validate a single script JSON file.
    
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # Check file exists
    if not filepath.exists():
        errors.append(f"File does not exist: {filepath}")
        return False, errors, warnings
    
    # Check file is readable
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            script_data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return False, errors, warnings
    except Exception as e:
        errors.append(f"Error reading file: {e}")
        return False, errors, warnings
    
    # Validate structure
    struct_valid, struct_errors = validate_script_structure(script_data, filepath)
    errors.extend(struct_errors)
    
    if not struct_valid:
        return False, errors, warnings
    
    # Validate content (warnings only)
    content_valid, content_warnings = validate_script_content(script_data, filepath)
    warnings.extend(content_warnings)
    
    return struct_valid and content_valid, errors, warnings


def find_script_files(directory: Path, pattern: str = "*.script.json") -> List[Path]:
    """Find all script JSON files in a directory."""
    return sorted(directory.glob(pattern))


def main():
    """Run validation on script JSON files."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate script JSON files')
    parser.add_argument('--dir', type=str, help='Directory containing script files')
    parser.add_argument('--file', type=str, help='Single script file to validate')
    parser.add_argument('--topic', type=str, help='Topic ID (searches in outputs/topic-ID)')
    args = parser.parse_args()
    
    # Determine which files to validate
    script_files = []
    
    if args.file:
        script_files = [Path(args.file)]
    elif args.dir:
        script_files = find_script_files(Path(args.dir))
    elif args.topic:
        # Look in outputs directory
        repo_root = Path(__file__).parent.parent
        output_dir = repo_root / 'outputs' / args.topic
        if output_dir.exists():
            script_files = find_script_files(output_dir)
        else:
            print(f"ERROR: Output directory not found: {output_dir}")
            return 1
    else:
        # Default: search in outputs directory
        repo_root = Path(__file__).parent.parent
        outputs_dir = repo_root / 'outputs'
        if outputs_dir.exists():
            script_files = find_script_files(outputs_dir, "**/*.script.json")
        else:
            print(f"ERROR: Outputs directory not found: {outputs_dir}")
            return 1
    
    if not script_files:
        print("No script JSON files found to validate")
        return 1
    
    print("=" * 80)
    print("SCRIPT JSON VALIDATION")
    print("=" * 80)
    print(f"Found {len(script_files)} script file(s) to validate\n")
    
    valid_count = 0
    invalid_count = 0
    warning_count = 0
    
    for script_file in script_files:
        print(f"Validating: {script_file.name}")
        print("-" * 80)
        
        is_valid, errors, warnings = validate_script_file(script_file)
        
        if errors:
            print("  ✗ ERRORS:")
            for error in errors:
                print(f"    - {error}")
            invalid_count += 1
        elif warnings:
            print("  ⚠ WARNINGS:")
            for warning in warnings:
                print(f"    - {warning}")
            valid_count += 1
            warning_count += 1
        else:
            print("  ✓ Valid")
            valid_count += 1
        
        print()
    
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total files:  {len(script_files)}")
    print(f"Valid:        {valid_count}")
    print(f"With warnings: {warning_count}")
    print(f"Invalid:      {invalid_count}")
    print("=" * 80)
    
    if invalid_count > 0:
        print("\n✗ Some script files have structural errors that will prevent TTS generation")
        return 1
    elif warning_count > 0:
        print("\n⚠ All script files are valid but some have content warnings")
        return 0
    else:
        print("\n✓ All script files are valid and ready for TTS generation")
        return 0


if __name__ == '__main__':
    sys.exit(main())
