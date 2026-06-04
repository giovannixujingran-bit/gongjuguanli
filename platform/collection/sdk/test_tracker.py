from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from collection.sdk import PlatformTracker, normalize_token_usage


def test_normalize_token_usage_openai_and_claude() -> None:
    openai = normalize_token_usage(
        "openai",
        {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )
    claude = normalize_token_usage("claude", {"input_tokens": 7, "output_tokens": 3})

    assert openai.prompt_tokens == 10
    assert openai.completion_tokens == 5
    assert openai.total_tokens == 15
    assert claude.prompt_tokens == 7
    assert claude.completion_tokens == 3
    assert claude.total_tokens == 10


def test_tracker_adds_entry_source_metadata() -> None:
    tracker = PlatformTracker(
        tool_id="demo-tool",
        endpoint_url="http://example.test/events",
        entry_source="direct",
        auth_method="session_token",
    )

    event = tracker.build_event(metadata={"feature": "demo"})

    assert event.metadata == {
        "entry_source": "direct",
        "auth_method": "session_token",
        "feature": "demo",
    }


def test_tracker_buffers_failed_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer_path = buffer_path_for("failed")
    tracker = PlatformTracker(
        tool_id="demo-tool",
        endpoint_url="http://example.test/events",
        buffer_path=buffer_path,
    )

    def fail_post(*_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "post", fail_post)

    event = tracker.record_usage()

    assert buffer_path.exists()
    assert str(event.record_id) in buffer_path.read_text(encoding="utf-8")


def test_tracker_flush_retries_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer_path = buffer_path_for("flush")
    tracker = PlatformTracker(
        tool_id="demo-tool",
        endpoint_url="http://example.test/events",
        buffer_path=buffer_path,
    )
    event = tracker.build_event()
    tracker.buffer_event(event)

    def ok_post(*_args: object, **_kwargs: object) -> httpx.Response:
        request = httpx.Request("POST", "http://example.test/events")
        return httpx.Response(status_code=202, request=request)

    monkeypatch.setattr(httpx, "post", ok_post)

    assert tracker.flush() == 1
    assert buffer_path.read_text(encoding="utf-8") == ""


def buffer_path_for(name: str) -> Path:
    return Path("tmp-tool-cache") / f"test-tracker-{name}-{uuid4()}.jsonl"
