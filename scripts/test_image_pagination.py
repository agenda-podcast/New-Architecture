#!/usr/bin/env python3
"""
Test pagination logic for Google Custom Search API image collection.
This test validates the new pagination implementation.
"""
import os
import sys
import tempfile
import json
from pathlib import Path
from datetime import date, datetime, timedelta

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from image_collector import (
    get_daily_usage,
    update_daily_usage,
    check_daily_limit,
    USAGE_TRACKING_FILE
)
from global_config import GOOGLE_SEARCH_DAILY_LIMIT


def test_daily_usage_tracking():
    """Test that daily usage tracking works correctly."""
    print("Testing daily usage tracking...")
    
    # Clear any existing tracking file
    if USAGE_TRACKING_FILE.exists():
        USAGE_TRACKING_FILE.unlink()
    
    # Get initial usage (should be 0)
    usage = get_daily_usage()
    if usage['count'] != 0:
        print(f"  ✗ Initial usage should be 0, got {usage['count']}")
        return False
    
    if usage['date'] != date.today().isoformat():
        print(f"  ✗ Usage date should be today, got {usage['date']}")
        return False
    
    print(f"  ✓ Initial usage: {usage['count']} results on {usage['date']}")
    
    # Update usage
    update_daily_usage(10)
    usage = get_daily_usage()
    if usage['count'] != 10:
        print(f"  ✗ Usage should be 10 after update, got {usage['count']}")
        return False
    
    print(f"  ✓ After update: {usage['count']} results")
    
    # Update again
    update_daily_usage(25)
    usage = get_daily_usage()
    if usage['count'] != 35:
        print(f"  ✗ Usage should be 35 after second update, got {usage['count']}")
        return False
    
    print(f"  ✓ After second update: {usage['count']} results")
    
    # Clean up
    if USAGE_TRACKING_FILE.exists():
        USAGE_TRACKING_FILE.unlink()
    
    print("  ✓ Daily usage tracking works correctly")
    return True


def test_daily_limit_check():
    """Test that daily limit checking works correctly."""
    print("Testing daily limit checking...")
    
    # Clear any existing tracking file
    if USAGE_TRACKING_FILE.exists():
        USAGE_TRACKING_FILE.unlink()
    
    # Test with no usage
    can_proceed, available = check_daily_limit(50)
    if not can_proceed:
        print(f"  ✗ Should be able to proceed with no usage")
        return False
    if available != 50:
        print(f"  ✗ Should have 50 results available, got {available}")
        return False
    
    print(f"  ✓ With no usage: can_proceed={can_proceed}, available={available}")
    
    # Update usage to near limit
    update_daily_usage(GOOGLE_SEARCH_DAILY_LIMIT - 20)
    
    # Test with near-limit usage
    can_proceed, available = check_daily_limit(50)
    if not can_proceed:
        print(f"  ✗ Should still be able to proceed with 20 remaining")
        return False
    if available != 20:
        print(f"  ✗ Should have 20 results available, got {available}")
        return False
    
    print(f"  ✓ Near limit: can_proceed={can_proceed}, available={available}")
    
    # Update to reach limit
    update_daily_usage(20)
    
    # Test at limit
    can_proceed, available = check_daily_limit(50)
    if can_proceed:
        print(f"  ✗ Should not be able to proceed at limit")
        return False
    if available != 0:
        print(f"  ✗ Should have 0 results available, got {available}")
        return False
    
    print(f"  ✓ At limit: can_proceed={can_proceed}, available={available}")
    
    # Clean up
    if USAGE_TRACKING_FILE.exists():
        USAGE_TRACKING_FILE.unlink()
    
    print("  ✓ Daily limit checking works correctly")
    return True


def test_date_reset():
    """Test that usage resets on a new day."""
    print("Testing date reset logic...")
    
    # Clear any existing tracking file
    if USAGE_TRACKING_FILE.exists():
        USAGE_TRACKING_FILE.unlink()
    
    # Set usage for today
    update_daily_usage(100)
    usage = get_daily_usage()
    if usage['count'] != 100:
        print(f"  ✗ Usage should be 100, got {usage['count']}")
        return False
    
    print(f"  ✓ Set usage to {usage['count']} for today")
    
    # Manually set the date to yesterday in the tracking file
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    
    with open(USAGE_TRACKING_FILE, 'w') as f:
        json.dump({'date': yesterday, 'count': 100}, f)
    
    print(f"  Changed tracking file date to {yesterday}")
    
    # Get usage - should reset to 0 for today
    usage = get_daily_usage()
    if usage['count'] != 0:
        print(f"  ✗ Usage should reset to 0 for new day, got {usage['count']}")
        return False
    
    if usage['date'] != date.today().isoformat():
        print(f"  ✗ Date should be today, got {usage['date']}")
        return False
    
    print(f"  ✓ Usage reset to {usage['count']} for new day ({usage['date']})")
    
    # Clean up
    if USAGE_TRACKING_FILE.exists():
        USAGE_TRACKING_FILE.unlink()
    
    print("  ✓ Date reset logic works correctly")
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("Image Collection Pagination Tests")
    print("="*60)
    
    tests = [
        test_daily_usage_tracking,
        test_daily_limit_check,
        test_date_reset,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        print()
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print()
    print("="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
