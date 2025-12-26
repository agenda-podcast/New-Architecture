#!/usr/bin/env python3
"""
Test that streaming completions use the ResponseStreamManager context manager.

This ensures we correctly iterate over the streaming response instead of the
manager object itself, which is not iterable.
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from openai_utils import create_openai_streaming_completion


class _FakeEvent:
    def __init__(self, delta: str):
        self.type = "response.output_text.delta"
        self.delta = delta


class _FakeResponseStream:
    def __init__(self, deltas):
        self._deltas = deltas
        self.closed = False

    def __iter__(self):
        for delta in self._deltas:
            yield _FakeEvent(delta)

    def close(self):
        self.closed = True


class _FakeResponseStreamManager:
    def __init__(self, deltas, tracker):
        self._deltas = deltas
        self._tracker = tracker
        self._stream = None

    def __enter__(self):
        self._tracker["entered"] = True
        self._stream = _FakeResponseStream(self._deltas)
        return self._stream

    def __exit__(self, exc_type, exc, tb):
        self._tracker["exited"] = True
        if self._stream:
            self._stream.close()


class _FakeResponses:
    def __init__(self, deltas, tracker):
        self._deltas = deltas
        self._tracker = tracker

    def stream(self, **params):
        self._tracker["params"] = params
        return _FakeResponseStreamManager(self._deltas, self._tracker)


class _FakeClient:
    def __init__(self, deltas, tracker):
        self.responses = _FakeResponses(deltas, tracker)


def test_streaming_completion_iterates_response_stream_not_manager():
    """Ensure streaming uses the manager context to obtain an iterable stream."""
    deltas = ["Hello ", "world!"]
    tracker = {"entered": False, "exited": False, "params": None}

    client = _FakeClient(deltas, tracker)

    result = create_openai_streaming_completion(
        client=client,
        model="gpt-5.2-pro",
        messages=[{"role": "user", "content": "Test"}],
    )

    assert result == "Hello world!"
    assert tracker["entered"] is True
    assert tracker["exited"] is True
    assert tracker["params"]["model"] == "gpt-5.2-pro"
    assert tracker["params"]["input"].strip() != ""
