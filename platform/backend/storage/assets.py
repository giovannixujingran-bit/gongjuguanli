from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, cast
from uuid import UUID, uuid4

from psycopg.rows import dict_row

from backend.storage.db import connect as db_connect


@dataclass(frozen=True)
class ReportAsset:
    asset_id: UUID
    filename: str
    title: str
    tool_id: str
    tool_name: str
    period_start: date
    period_end: date
    html: str
    created_by: str
    created_at: datetime


class ReportAssetRepository(Protocol):
    def create_report_asset(
        self,
        *,
        filename: str,
        title: str,
        tool_id: str,
        tool_name: str,
        period_start: date,
        period_end: date,
        html: str,
        created_by: str,
    ) -> ReportAsset:
        """Store one generated HTML report as an asset."""

    def list_report_assets(self, *, limit: int = 50) -> list[ReportAsset]:
        """Newest-first report assets."""

    def get_report_asset(self, asset_id: UUID) -> ReportAsset | None:
        """Find one report asset by id."""


class PostgresReportAssetRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def create_report_asset(
        self,
        *,
        filename: str,
        title: str,
        tool_id: str,
        tool_name: str,
        period_start: date,
        period_end: date,
        html: str,
        created_by: str,
    ) -> ReportAsset:
        params = {
            "asset_id": uuid4(),
            "filename": filename,
            "title": title,
            "tool_id": tool_id,
            "tool_name": tool_name,
            "period_start": period_start,
            "period_end": period_end,
            "html": html,
            "created_by": created_by,
        }
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(INSERT_REPORT_ASSET_SQL, params)
                row = cursor.fetchone()
        if row is None:
            raise RuntimeError("report asset insert returned no row")
        return row_to_asset(row)

    def list_report_assets(self, *, limit: int = 50) -> list[ReportAsset]:
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(LIST_REPORT_ASSETS_SQL, {"limit": limit})
                rows = cursor.fetchall()
        return [row_to_asset(row) for row in rows]

    def get_report_asset(self, asset_id: UUID) -> ReportAsset | None:
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(GET_REPORT_ASSET_SQL, {"asset_id": asset_id})
                row = cursor.fetchone()
        if row is None:
            return None
        return row_to_asset(row)


def row_to_asset(row: dict[str, object]) -> ReportAsset:
    return ReportAsset(
        asset_id=cast(UUID, row["asset_id"]),
        filename=cast(str, row["filename"]),
        title=cast(str, row["title"]),
        tool_id=cast(str, row["tool_id"]),
        tool_name=cast(str, row["tool_name"]),
        period_start=cast(date, row["period_start"]),
        period_end=cast(date, row["period_end"]),
        html=cast(str, row["html"]),
        created_by=cast(str, row["created_by"]),
        created_at=cast(datetime, row["created_at"]),
    )


INSERT_REPORT_ASSET_SQL = """
INSERT INTO report_asset (
    asset_id,
    filename,
    title,
    tool_id,
    tool_name,
    period_start,
    period_end,
    html,
    created_by
) VALUES (
    %(asset_id)s,
    %(filename)s,
    %(title)s,
    %(tool_id)s,
    %(tool_name)s,
    %(period_start)s,
    %(period_end)s,
    %(html)s,
    %(created_by)s
)
RETURNING
    asset_id,
    filename,
    title,
    tool_id,
    tool_name,
    period_start,
    period_end,
    html,
    created_by,
    created_at
"""

LIST_REPORT_ASSETS_SQL = """
SELECT
    asset_id,
    filename,
    title,
    tool_id,
    tool_name,
    period_start,
    period_end,
    html,
    created_by,
    created_at
FROM report_asset
ORDER BY created_at DESC
LIMIT %(limit)s
"""

GET_REPORT_ASSET_SQL = """
SELECT
    asset_id,
    filename,
    title,
    tool_id,
    tool_name,
    period_start,
    period_end,
    html,
    created_by,
    created_at
FROM report_asset
WHERE asset_id = %(asset_id)s
"""
