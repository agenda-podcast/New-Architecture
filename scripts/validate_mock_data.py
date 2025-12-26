#!/usr/bin/env python3
"""
Validate mock response data word counts.

This script checks that all mock response files have dialogue content
that matches (or is close to) the target word counts defined in the
content type specifications.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from global_config import CONTENT_TYPES


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def analyze_pass_a_response(file_path: Path) -> Dict:
    """Analyze Pass A response file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = []
    
    # Check L1 content
    if 'l1_content' in data:
        l1 = data['l1_content']
        code = l1.get('code', 'L1')
        target = l1.get('target_words', CONTENT_TYPES['long']['target_words'])
        actual = l1.get('actual_words', 0)
        
        # Count from script if actual_words not set
        if actual == 0 and 'script' in l1:
            actual = count_words(l1['script'])
        
        results.append({
            'code': code,
            'type': 'long',
            'target': target,
            'actual': actual,
            'percentage': (actual / target * 100) if target > 0 else 0,
            'status': 'OK' if abs(actual - target) / target < 0.1 else 'NEEDS_FIX'
        })
    
    return {'file': file_path.name, 'content': results}


def analyze_pass_b_response(file_path: Path) -> Dict:
    """Analyze Pass B response file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = []
    
    # Check all content pieces
    if 'content' in data:
        for item in data['content']:
            code = item.get('code', 'UNKNOWN')
            content_type = item.get('type', 'unknown')
            target = item.get('target_words', 0)
            
            # Get target from CONTENT_TYPES if not in item
            if target == 0 and content_type in CONTENT_TYPES:
                target = CONTENT_TYPES[content_type]['target_words']
            
            actual = item.get('actual_words', 0)
            
            # Count from script if actual_words not set
            if actual == 0 and 'script' in item:
                actual = count_words(item['script'])
            
            results.append({
                'code': code,
                'type': content_type,
                'target': target,
                'actual': actual,
                'percentage': (actual / target * 100) if target > 0 else 0,
                'status': 'OK' if abs(actual - target) / target < 0.1 else 'NEEDS_FIX'
            })
    
    return {'file': file_path.name, 'content': results}


def print_analysis_table(analysis_results: List[Dict]):
    """Print analysis results as a table."""
    print("\n" + "=" * 90)
    print("MOCK DATA WORD COUNT ANALYSIS")
    print("=" * 90)
    
    total_ok = 0
    total_needs_fix = 0
    
    for file_result in analysis_results:
        print(f"\n{file_result['file']}:")
        print("-" * 90)
        print(f"{'Code':<6} {'Type':<8} {'Target':<8} {'Actual':<8} {'%':<8} {'Status':<12}")
        print("-" * 90)
        
        for item in file_result['content']:
            code = item['code']
            content_type = item['type']
            target = item['target']
            actual = item['actual']
            percentage = item['percentage']
            status = item['status']
            
            status_symbol = '✓' if status == 'OK' else '✗'
            
            print(f"{code:<6} {content_type:<8} {target:<8} {actual:<8} {percentage:>6.1f}%  {status_symbol} {status}")
            
            if status == 'OK':
                total_ok += 1
            else:
                total_needs_fix += 1
    
    print("\n" + "=" * 90)
    print(f"SUMMARY: {total_ok} OK, {total_needs_fix} NEED FIX")
    print("=" * 90)
    
    if total_needs_fix > 0:
        print("\n⚠ Some content pieces don't match their target word counts.")
        print("  Content should be within ±10% of target.")
    else:
        print("\n✓ All content pieces match their target word counts!")
    
    return total_needs_fix == 0


def main():
    """Run validation."""
    # Get mock responses directory
    repo_root = Path(__file__).parent.parent
    mock_dir = repo_root / 'test_data' / 'mock_responses'
    
    if not mock_dir.exists():
        print(f"ERROR: Mock responses directory not found: {mock_dir}")
        return 1
    
    # Analyze all mock response files
    results = []
    
    pass_a_file = mock_dir / 'pass_a_response.json'
    if pass_a_file.exists():
        results.append(analyze_pass_a_response(pass_a_file))
    else:
        print(f"Warning: {pass_a_file} not found")
    
    pass_b_file = mock_dir / 'pass_b_response.json'
    if pass_b_file.exists():
        results.append(analyze_pass_b_response(pass_b_file))
    else:
        print(f"Warning: {pass_b_file} not found")
    
    # Print analysis
    if results:
        all_ok = print_analysis_table(results)
        return 0 if all_ok else 1
    else:
        print("ERROR: No mock response files found to analyze")
        return 1


if __name__ == '__main__':
    sys.exit(main())
