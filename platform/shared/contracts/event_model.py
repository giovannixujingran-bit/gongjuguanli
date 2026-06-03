# 自动生成，勿手改 —— 由 tools/generate_contracts.py 从 shared/schema/event.schema.json 生成
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UsageEvent(BaseModel):
    """统一事件记录。字段定义来自 shared/schema/event.schema.json。"""

    model_config = ConfigDict(extra="forbid")

    record_id: UUID = ...
    schema_version: str = Field(..., pattern='^v[0-9]+\\.[0-9]+$')
    tool_id: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)
    start_time: datetime = ...
    end_time: datetime = ...
    duration_ms: int = Field(..., ge=0)
    status: Literal['success', 'failed', 'timeout'] = ...
    ingested_at: datetime | None = None
    model: str | None = None
    prompt_tokens: int | None = Field(None, ge=0)
    completion_tokens: int | None = Field(None, ge=0)
    total_tokens: int | None = Field(None, ge=0)
    cost: Decimal | None = Field(None, ge=0)
    cost_source: Literal['source', 'computed'] | None = None
    user_id: str | None = None
    team_id: str | None = None
    result_quality: float | str | None = None
    adopted: bool | None = None
    input_content: str | None = None
    output_content: str | None = None
    metadata: dict[str, Any] | None = None
