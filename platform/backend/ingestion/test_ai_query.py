from __future__ import annotations

import pytest

from backend.ingestion.ai_query import AiQueryError, extract_answer_text


def test_extract_answer_text_joins_all_text_parts() -> None:
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "你好，"}, {"text": "这是回答。"}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"totalTokenCount": 12},
    }

    assert extract_answer_text(payload) == "你好，这是回答。"


def test_extract_answer_text_rejects_malformed_payloads() -> None:
    bad_payloads: list[object] = [
        "not a dict",
        {},
        {"candidates": []},
        {"candidates": [{"content": {}}]},
        {"candidates": [{"content": {"parts": [{"inlineData": {}}]}}]},
    ]

    for payload in bad_payloads:
        with pytest.raises(AiQueryError):
            extract_answer_text(payload)
