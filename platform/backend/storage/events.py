from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.storage.db import connect as db_connect
from shared.contracts.event_model import UsageEvent


@dataclass(frozen=True)
class StoredEvent:
    record_id: UUID
    ingested_at: datetime
    inserted: bool


@dataclass(frozen=True)
class EventRow:
    record_id: UUID
    tool_id: str
    model: str | None
    user_id: str
    # 工具自报的 metadata.chapter_type（如 aird-report 按报告章节逐次调用）；没报则为 None。
    chapter: str | None
    input_preview: str | None
    output_preview: str | None
    status: str
    total_tokens: int | None
    duration_ms: int
    start_time: datetime


@dataclass(frozen=True)
class EventPage:
    rows: list[EventRow]
    total: int


@dataclass(frozen=True)
class DailyUsage:
    day: str
    events: int
    tokens: int


@dataclass(frozen=True)
class UsageSummary:
    total_events: int
    success_events: int
    avg_duration_ms: float | None
    total_tokens: int
    daily: list[DailyUsage]
    events_by_tool: dict[str, int]


class UsageEventRepository(Protocol):
    def insert_event(self, event: UsageEvent, *, ingested_at: datetime) -> StoredEvent:
        """Store one event idempotently by record_id."""


class UsageEventReader(Protocol):
    def list_events(
        self,
        *,
        tool_id: str | None = None,
        status: str | None = None,
        since_hours: int | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> EventPage:
        """Newest-first rows for the data page. metadata.test=true is excluded."""

    def summarize(self) -> UsageSummary:
        """Raw aggregates for non-test traffic. Formula-heavy metrics stay out for now."""


class PostgresUsageEventRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def insert_event(self, event: UsageEvent, *, ingested_at: datetime) -> StoredEvent:
        params = event_to_db_params(event, ingested_at=ingested_at)
        with db_connect(self._database_url) as connection:
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


class PostgresUsageEventReader:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def list_events(
        self,
        *,
        tool_id: str | None = None,
        status: str | None = None,
        since_hours: int | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> EventPage:
        where, params = build_event_filters(tool_id=tool_id, status=status, since_hours=since_hours)
        params["limit"] = limit
        params["offset"] = offset
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(f"SELECT count(*) AS total FROM usage_event WHERE {where}", params)
                counted = cursor.fetchone()
                total = 0 if counted is None else int(counted["total"])
                cursor.execute(
                    f"""
                    SELECT record_id, tool_id, model, user_id,
                           metadata ->> 'chapter_type' AS chapter,
                           left(input_content, 80) AS input_preview,
                           left(output_content, 80) AS output_preview,
                           status, total_tokens, duration_ms, start_time
                    FROM usage_event
                    WHERE {where}
                    ORDER BY start_time DESC
                    LIMIT %(limit)s OFFSET %(offset)s
                    """,
                    params,
                )
                rows = [
                    EventRow(
                        record_id=row["record_id"],
                        tool_id=str(row["tool_id"]),
                        model=None if row["model"] is None else str(row["model"]),
                        user_id=str(row["user_id"]),
                        chapter=None if row["chapter"] is None else str(row["chapter"]),
                        input_preview=row["input_preview"],
                        output_preview=row["output_preview"],
                        status=str(row["status"]),
                        total_tokens=row["total_tokens"],
                        duration_ms=int(row["duration_ms"]),
                        start_time=row["start_time"],
                    )
                    for row in cursor.fetchall()
                ]
        return EventPage(rows=rows, total=total)

    def summarize(self) -> UsageSummary:
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT count(*) AS total_events,
                           count(*) FILTER (WHERE status = 'success') AS success_events,
                           avg(duration_ms) AS avg_duration_ms,
                           coalesce(sum(total_tokens), 0) AS total_tokens
                    FROM usage_event
                    WHERE {EXCLUDE_TEST_SQL}
                    """
                )
                totals = cursor.fetchone()
                cursor.execute(
                    f"""
                    SELECT start_time::date AS day,
                           count(*) AS events,
                           coalesce(sum(total_tokens), 0) AS tokens
                    FROM usage_event
                    WHERE {EXCLUDE_TEST_SQL}
                      AND start_time >= now() - interval '14 days'
                    GROUP BY 1
                    ORDER BY 1
                    """
                )
                daily = [
                    DailyUsage(
                        day=row["day"].isoformat(),
                        events=int(row["events"]),
                        tokens=int(row["tokens"]),
                    )
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    f"""
                    SELECT tool_id, count(*) AS events
                    FROM usage_event
                    WHERE {EXCLUDE_TEST_SQL}
                    GROUP BY tool_id
                    """
                )
                by_tool = {str(row["tool_id"]): int(row["events"]) for row in cursor.fetchall()}
        if totals is None:
            raise RuntimeError("usage summary query returned no row")
        avg_duration = totals["avg_duration_ms"]
        return UsageSummary(
            total_events=int(totals["total_events"]),
            success_events=int(totals["success_events"]),
            avg_duration_ms=None if avg_duration is None else float(avg_duration),
            total_tokens=int(totals["total_tokens"]),
            daily=daily,
            events_by_tool=by_tool,
        )


EXCLUDE_TEST_SQL = "NOT coalesce((metadata ->> 'test')::boolean, false)"


def build_event_filters(
    *,
    tool_id: str | None,
    status: str | None,
    since_hours: int | None,
) -> tuple[str, dict[str, object]]:
    clauses = [EXCLUDE_TEST_SQL]
    params: dict[str, object] = {}
    if tool_id is not None:
        clauses.append("tool_id = %(tool_id)s")
        params["tool_id"] = tool_id
    if status is not None:
        clauses.append("status = %(status)s")
        params["status"] = status
    if since_hours is not None:
        clauses.append("start_time >= now() - make_interval(hours => %(since_hours)s)")
        params["since_hours"] = since_hours
    return " AND ".join(clauses), params


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
