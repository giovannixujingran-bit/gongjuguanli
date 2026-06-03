from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from shared.contracts.event_model import UsageEvent


@dataclass(frozen=True)
class StoredEvent:
    record_id: UUID
    ingested_at: datetime
    inserted: bool


class UsageEventRepository(Protocol):
    def insert_event(self, event: UsageEvent, *, ingested_at: datetime) -> StoredEvent:
        """Store one event idempotently by record_id."""


class PostgresUsageEventRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def insert_event(self, event: UsageEvent, *, ingested_at: datetime) -> StoredEvent:
        params = event_to_db_params(event, ingested_at=ingested_at)
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(INSERT_EVENT_SQL, params)
                row = cursor.fetchone()
                if row is not None:
                    return StoredEvent(
                        record_id=row["record_id"],
                        ingested_at=row["ingested_at"],
                        inserted=True,
                    )

                cursor.execute(
                    (
                        "SELECT record_id, ingested_at FROM usage_event "
                        "WHERE record_id = %(record_id)s"
                    ),
                    {"record_id": event.record_id},
                )
                existing = cursor.fetchone()

        if existing is None:
            raise RuntimeError("record_id conflict lookup failed")

        return StoredEvent(
            record_id=existing["record_id"],
            ingested_at=existing["ingested_at"],
            inserted=False,
        )


def event_to_db_params(event: UsageEvent, *, ingested_at: datetime) -> dict[str, object]:
    return {
        "record_id": event.record_id,
        "schema_version": event.schema_version,
        "tool_id": event.tool_id,
        "conversation_id": event.conversation_id,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "duration_ms": event.duration_ms,
        "status": event.status,
        "ingested_at": ingested_at,
        "model": event.model,
        "prompt_tokens": event.prompt_tokens,
        "completion_tokens": event.completion_tokens,
        "total_tokens": event.total_tokens,
        "cost": event.cost,
        "cost_source": event.cost_source,
        "user_id": event.user_id,
        "team_id": event.team_id,
        "result_quality": numeric_quality(event.result_quality),
        "adopted": event.adopted,
        "input_content": event.input_content,
        "output_content": event.output_content,
        "metadata": Jsonb(event.metadata or {}),
    }


def numeric_quality(value: float | str | None) -> float | None:
    if value is None or isinstance(value, str):
        return None
    return float(value)


INSERT_EVENT_SQL = """
INSERT INTO usage_event (
    record_id, schema_version, tool_id, conversation_id, start_time, end_time,
    duration_ms, status, ingested_at, model, prompt_tokens, completion_tokens,
    total_tokens, cost, cost_source, user_id, team_id, result_quality, adopted,
    input_content, output_content, metadata
) VALUES (
    %(record_id)s, %(schema_version)s, %(tool_id)s, %(conversation_id)s,
    %(start_time)s, %(end_time)s, %(duration_ms)s, %(status)s, %(ingested_at)s,
    %(model)s, %(prompt_tokens)s, %(completion_tokens)s, %(total_tokens)s,
    %(cost)s, %(cost_source)s, %(user_id)s, %(team_id)s, %(result_quality)s,
    %(adopted)s, %(input_content)s, %(output_content)s, %(metadata)s
)
ON CONFLICT (record_id) DO NOTHING
RETURNING record_id, ingested_at
"""
