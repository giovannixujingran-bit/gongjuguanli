from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg

from shared.schema_version import CURRENT_SCHEMA_VERSION

DEFAULT_API_URL = "http://127.0.0.1:8000/events"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1.5 real database smoke test.")
    parser.add_argument("--api-url", default=os.environ.get("INGESTION_API_URL", DEFAULT_API_URL))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required.")

    record_id = str(uuid4())
    payload = sample_payload(record_id)
    response = httpx.post(args.api_url, json=payload, timeout=10)
    response.raise_for_status()

    stored = fetch_event(args.database_url, record_id)
    if stored is None:
        raise SystemExit(f"event {record_id} was accepted but not found in usage_event.")

    print(
        json.dumps(
            {
                "api_status": response.status_code,
                "record_id": record_id,
                "tool_id": stored["tool_id"],
                "user_id": stored["user_id"],
                "metadata": stored["metadata"],
            },
            ensure_ascii=False,
            default=str,
            indent=2,
        )
    )


def sample_payload(record_id: str) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "record_id": record_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "tool_id": "smoke-demo-tool",
        "conversation_id": record_id,
        "start_time": now.isoformat(),
        "end_time": now.isoformat(),
        "duration_ms": 0,
        "status": "success",
        "user_id": "anonymous",
        "metadata": {
            "entry_source": "unknown",
            "auth_method": "none",
            "smoke_script": str(Path(__file__).relative_to(Path.cwd())),
        },
    }


def fetch_event(database_url: str, record_id: str) -> dict[str, object] | None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tool_id, user_id, metadata FROM usage_event WHERE record_id = %s",
                (record_id,),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    return {"tool_id": row[0], "user_id": row[1], "metadata": row[2]}


if __name__ == "__main__":
    main()
