from __future__ import annotations

import os
from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel

from backend.storage.events import PostgresUsageEventRepository, StoredEvent, UsageEventRepository
from shared.contracts.event_model import UsageEvent


class EventIngested(BaseModel):
    record_id: UUID
    ingested_at: datetime
    inserted: bool


def create_app() -> FastAPI:
    application = FastAPI(title="内部工具汇总接入 API")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post(
        "/events",
        response_model=EventIngested,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def ingest_event(
        event: UsageEvent,
        repository: UsageEventRepository = Depends(get_repository),
    ) -> EventIngested:
        normalized = normalize_event(event)
        ingested_at = datetime.now(UTC)
        try:
            stored = repository.insert_event(normalized, ingested_at=ingested_at)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="event storage failed",
            ) from exc
        return event_response(stored)

    return application


def normalize_event(event: UsageEvent) -> UsageEvent:
    return event.model_copy(
        update={
            "user_id": event.user_id or "anonymous",
            "metadata": event.metadata or {},
            "ingested_at": None,
        }
    )


def event_response(stored: StoredEvent) -> EventIngested:
    return EventIngested(
        record_id=stored.record_id,
        ingested_at=stored.ingested_at,
        inserted=stored.inserted,
    )


@lru_cache(maxsize=1)
def get_database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if value is None or not value.strip():
        raise RuntimeError("DATABASE_URL is required")
    return value


@lru_cache(maxsize=1)
def get_repository() -> UsageEventRepository:
    return PostgresUsageEventRepository(get_database_url())


app = create_app()
