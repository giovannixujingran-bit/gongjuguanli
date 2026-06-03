from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from fastapi.testclient import TestClient

from backend.ingestion.app import create_app, get_repository
from backend.storage.events import StoredEvent
from shared.contracts.event_model import UsageEvent

SAMPLE_RECORD_ID = "018f6b43-2e69-7a2b-9b34-111111111111"


@dataclass
class MemoryUsageEventRepository:
    events: dict[UUID, tuple[UsageEvent, datetime]] = field(default_factory=dict)

    def insert_event(self, event: UsageEvent, *, ingested_at: datetime) -> StoredEvent:
        existing = self.events.get(event.record_id)
        if existing is not None:
            return StoredEvent(
                record_id=event.record_id,
                ingested_at=existing[1],
                inserted=False,
            )

        self.events[event.record_id] = (event, ingested_at)
        return StoredEvent(record_id=event.record_id, ingested_at=ingested_at, inserted=True)


def test_ingest_event_accepts_simulated_payload_and_defaults_anonymous_user() -> None:
    repository = MemoryUsageEventRepository()
    client = client_with_repository(repository)

    response = client.post("/events", json=sample_payload(user_id=None))

    assert response.status_code == 202
    assert response.json()["record_id"] == SAMPLE_RECORD_ID
    assert response.json()["inserted"] is True
    stored_event = repository.events[UUID(SAMPLE_RECORD_ID)][0]
    assert stored_event.user_id == "anonymous"
    assert stored_event.metadata == {}
    assert stored_event.ingested_at is None


def test_ingest_event_is_idempotent_by_record_id() -> None:
    repository = MemoryUsageEventRepository()
    client = client_with_repository(repository)

    first = client.post("/events", json=sample_payload())
    second = client.post("/events", json=sample_payload())

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["inserted"] is True
    assert second.json()["inserted"] is False
    assert len(repository.events) == 1


def test_ingest_event_rejects_missing_required_field() -> None:
    repository = MemoryUsageEventRepository()
    client = client_with_repository(repository)
    payload = sample_payload()
    del payload["tool_id"]

    response = client.post("/events", json=payload)

    assert response.status_code == 422
    assert repository.events == {}


def client_with_repository(repository: MemoryUsageEventRepository) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    return TestClient(app)


def sample_payload(*, user_id: str | None = "user-001") -> dict[str, object]:
    payload: dict[str, object] = {
        "record_id": SAMPLE_RECORD_ID,
        "schema_version": "v0.2",
        "tool_id": "mock-tool",
        "conversation_id": "mock-conversation",
        "start_time": "2026-06-03T08:00:00Z",
        "end_time": "2026-06-03T08:00:02Z",
        "duration_ms": 2000,
        "status": "success",
        "model": "mock-model",
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
        "cost": 0.001,
        "cost_source": "source",
        "team_id": "team-a",
        "result_quality": 0.95,
        "adopted": True,
        "input_content": "mock input",
        "output_content": "mock output",
    }
    if user_id is not None:
        payload["user_id"] = user_id
    return payload
