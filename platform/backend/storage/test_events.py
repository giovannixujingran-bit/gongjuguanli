from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from backend.storage.events import event_to_db_params, numeric_quality
from shared.contracts.event_model import UsageEvent


def test_event_to_db_params_uses_server_ingested_at_and_metadata_default() -> None:
    ingested_at = datetime(2026, 6, 3, 8, 0, tzinfo=UTC)
    event = UsageEvent.model_validate(
        {
            "record_id": "018f6b43-2e69-7a2b-9b34-111111111111",
            "schema_version": "v0.2",
            "tool_id": "mock-tool",
            "conversation_id": "mock-conversation",
            "start_time": "2026-06-03T08:00:00Z",
            "end_time": "2026-06-03T08:00:02Z",
            "duration_ms": 2000,
            "status": "success",
            "user_id": "anonymous",
        }
    )

    params = event_to_db_params(event, ingested_at=ingested_at)

    assert params["record_id"] == UUID("018f6b43-2e69-7a2b-9b34-111111111111")
    assert params["ingested_at"] == ingested_at
    assert params["user_id"] == "anonymous"
    assert params["metadata"] is not None


def test_numeric_quality_keeps_numeric_values_and_ignores_enum_labels() -> None:
    assert numeric_quality(0.8) == 0.8
    assert numeric_quality("good") is None
    assert numeric_quality(None) is None
