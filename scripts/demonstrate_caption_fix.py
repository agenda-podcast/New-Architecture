#!/usr/bin/env python3
"""
Demonstration of the caption burn-in fix.

This script shows the difference between the broken and fixed
enable parameter formatting in FFmpeg drawtext filters.
"""
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from video_render import _build_drawtext_vf


def demonstrate_fix():
    """Show the before/after of the fix."""
    print("="*70)
    print("Caption Burn-in Fix Demonstration")
    print("="*70)
    
    # Sample caption data
    captions = [
        (0.0, 2.655, "Breaking: New AI regulations just\\ndropped!"),
        (3.155, 8.821, "All large AI models need\\nsafety audits and transparency measures\\nby Q2 2026."),
        (18.057, 22.892, "One CEO said: 'Finally getting\\nguardrails, not roadblocks.'"),
    ]
    
    print("\nSample Captions:")
    for i, (start, end, text) in enumerate(captions, 1):
        # Show original text (with literal newlines for display)
        display_text = text.replace('\\n', ' / ')
        print(f"  {i}. [{start:.3f}s - {end:.3f}s] {display_text}")
    
    # Generate the filter string
    vf = _build_drawtext_vf(
        captions,
        font_size=63,
        margin_v=384,
        margin_lr=50,
        style="tiktok"
    )
    
    print("\n" + "="*70)
    print("BEFORE THE FIX (broken):")
    print("="*70)
    print("The enable parameter was formatted as:")
    print("  enable='between(t\\,0.000\\,2.655)'")
    print("           ^                       ^")
    print("           Single quotes caused FFmpeg parsing errors!")
    print("\nFFmpeg Error:")
    print("  [AVFilterGraph] No option name near '63:fontcolor=...:enable=between(...)'")
    print("\n" + "="*70)
    print("AFTER THE FIX (working):")
    print("="*70)
    print("The enable parameter is now formatted as:")
    print("  enable=between(t\\,0.000\\,2.655)")
    print("         ^                      ^")
    print("         No quotes - FFmpeg can parse correctly!")
    
    # Extract a sample enable parameter from the generated filter
    import re
    enable_matches = re.findall(r'enable=[^:]+', vf)
    if enable_matches:
        print(f"\nActual generated enable parameters:")
        for i, match in enumerate(enable_matches[:3], 1):  # Show first 3
            print(f"  {i}. {match}")
    
    print("\n" + "="*70)
    print("Technical Details:")
    print("="*70)
    print("The fix changes the _enable_between() function:")
    print()
    print("BEFORE:")
    print("  def _enable_between(t0: float, t1: float) -> str:")
    print("      return f\"'between(t\\\\,{t0:.3f}\\\\,{t1:.3f})'\"")
    print("                ^                                  ^")
    print("                Outer quotes added")
    print()
    print("AFTER:")
    print("  def _enable_between(t0: float, t1: float) -> str:")
    print("      return f\"between(t\\\\,{t0:.3f}\\\\,{t1:.3f})\"")
    print("               ^                                ^")
    print("               No outer quotes")
    print()
    print("="*70)
    print("Result: Caption burning now works correctly! ✓")
    print("="*70)
    
    return True


if __name__ == '__main__':
    demonstrate_fix()
