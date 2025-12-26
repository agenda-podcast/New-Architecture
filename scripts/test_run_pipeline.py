#!/usr/bin/env python3
"""
Regression tests for pipeline behavior.

Focuses on ensuring that video rendering failures are treated as fatal so the
pipeline does not report success when videos are missing.
"""
import sys

import run_pipeline


# Stub out expensive steps; these tests only care about control flow.
run_pipeline.script_generate.generate_for_topic = lambda topic, date: True
run_pipeline.tts_generate.generate_for_topic = lambda topic, date: True


def test_pipeline_fails_when_video_render_fails():
    """Pipeline should stop when video rendering fails."""
    run_pipeline.video_render.render_for_topic = lambda topic, date: False
    result = run_pipeline.run_for_topic(
        "topic-test",
        "20250101",
        skip_video=False,
        skip_validation=True,
    )
    assert result is False, "Pipeline must return False when video render fails"
    print("✓ Pipeline correctly fails on video render error")


def test_pipeline_succeeds_when_video_render_succeeds():
    """Pipeline should succeed when video rendering succeeds."""
    run_pipeline.video_render.render_for_topic = lambda topic, date: True
    result = run_pipeline.run_for_topic(
        "topic-test",
        "20250101",
        skip_video=False,
        skip_validation=True,
    )
    assert result is True, "Pipeline should succeed when video render succeeds"
    print("✓ Pipeline succeeds when video render passes")


def main():
    print("=" * 60)
    print("Run Pipeline Tests")
    print("=" * 60)

    try:
        test_pipeline_fails_when_video_render_fails()
        test_pipeline_succeeds_when_video_render_succeeds()
        print("\n" + "=" * 60)
        print("✓ All pipeline tests passed")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
