from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx

from shared.contracts.event_model import UsageEvent
from shared.schema_version import CURRENT_SCHEMA_VERSION

EntrySource = Literal["portal", "direct", "unknown"]
AuthMethod = Literal["launch_token", "session_token", "none"]


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class PlatformTracker:
    def __init__(
        self,
        *,
        tool_id: str,
        endpoint_url: str,
        auth_token: str | None = None,
        user_id: str | None = None,
        entry_source: EntrySource = "unknown",
        auth_method: AuthMethod = "none",
        buffer_path: Path | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.tool_id = tool_id
        self.endpoint_url = endpoint_url
        self.auth_token = auth_token
        self.user_id = user_id
        self.entry_source = entry_source
        self.auth_method = auth_method
        self.buffer_path = buffer_path
        self.timeout_seconds = timeout_seconds
        # buffer 文件读写加锁：自动重发后台线程与手动 flush 可能并发，避免互相覆盖。
        self._buffer_lock = threading.Lock()

    def record_usage(
        self,
        *,
        conversation_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        duration_ms: int | None = None,
        status: Literal["success", "failed", "timeout"] = "success",
        model: str | None = None,
        token_usage: TokenUsage | None = None,
        input_content: str | None = None,
        output_content: str | None = None,
        metadata: dict[str, Any] | None = None,
        background_send: bool = False,
    ) -> UsageEvent:
        # background_send 只决定「上报这一条记录是否丢到后台线程发」，
        # 与契约 §四「异步任务两段式（提交→查状态）」无关，别混淆。
        event = self.build_event(
            conversation_id=conversation_id,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            status=status,
            model=model,
            token_usage=token_usage,
            input_content=input_content,
            output_content=output_content,
            metadata=metadata,
        )
        if background_send:
            self.send_in_background(event)
        else:
            self.report(event)
        return event

    def build_event(
        self,
        *,
        conversation_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        duration_ms: int | None = None,
        status: Literal["success", "failed", "timeout"] = "success",
        model: str | None = None,
        token_usage: TokenUsage | None = None,
        input_content: str | None = None,
        output_content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageEvent:
        record_id = uuid4()
        started_at = start_time or datetime.now(UTC)
        ended_at = end_time or started_at
        measured_duration = duration_ms
        if measured_duration is None:
            measured_duration = max(int((ended_at - started_at).total_seconds() * 1000), 0)

        merged_metadata = {
            "entry_source": self.entry_source,
            "auth_method": self.auth_method,
            **(metadata or {}),
        }
        usage = token_usage or TokenUsage()
        return UsageEvent(
            record_id=record_id,
            schema_version=CURRENT_SCHEMA_VERSION,
            tool_id=self.tool_id,
            conversation_id=conversation_id or str(record_id),
            start_time=started_at,
            end_time=ended_at,
            duration_ms=measured_duration,
            status=status,
            model=model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cost=None,
            user_id=self.user_id,
            input_content=input_content,
            output_content=output_content,
            metadata=merged_metadata,
        )

    def report(self, event: UsageEvent) -> None:
        try:
            response = httpx.post(
                self.endpoint_url,
                json=event_payload(event),
                headers=self.auth_headers(),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            self.buffer_event(event)
            return
        # 上报成功 = 平台此刻可达，顺带把之前积压的 buffer 重发掉（重试队列的自愈点）。
        if self.buffer_path is not None and self.buffer_path.exists():
            self.flush()

    def send_in_background(self, event: UsageEvent) -> threading.Thread:
        thread = threading.Thread(target=self.report, args=(event,), daemon=True)
        thread.start()
        return thread

    def flush(self) -> int:
        if self.buffer_path is None:
            return 0

        with self._buffer_lock:
            if not self.buffer_path.exists():
                return 0
            pending = [
                UsageEvent.model_validate(json.loads(line))
                for line in self.buffer_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            sent = 0
            remaining: list[UsageEvent] = []
            for event in pending:
                try:
                    response = httpx.post(
                        self.endpoint_url,
                        json=event_payload(event),
                        headers=self.auth_headers(),
                        timeout=self.timeout_seconds,
                    )
                    response.raise_for_status()
                    sent += 1
                except httpx.HTTPError:
                    remaining.append(event)

            write_buffer(self.buffer_path, remaining)
            return sent

    def buffer_event(self, event: UsageEvent) -> None:
        if self.buffer_path is None:
            return
        with self._buffer_lock:
            self.buffer_path.parent.mkdir(parents=True, exist_ok=True)
            with self.buffer_path.open("a", encoding="utf-8", newline="\n") as file:
                file.write(json.dumps(event_payload(event), ensure_ascii=False) + "\n")

    def auth_headers(self) -> dict[str, str]:
        if self.auth_token is None:
            return {}
        return {"Authorization": f"Bearer {self.auth_token}"}


def event_payload(event: UsageEvent) -> dict[str, Any]:
    return event.model_dump(mode="json", exclude_none=True)


def write_buffer(buffer_path: Path, events: list[UsageEvent]) -> None:
    if not events:
        buffer_path.parent.mkdir(parents=True, exist_ok=True)
        buffer_path.write_text("", encoding="utf-8", newline="\n")
        return
    buffer_path.write_text(
        "\n".join(json.dumps(event_payload(event), ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def normalize_token_usage(provider: str, usage: dict[str, Any]) -> TokenUsage:
    if provider == "openai":
        prompt = int_or_none(usage.get("prompt_tokens"))
        completion = int_or_none(usage.get("completion_tokens"))
        total = int_or_none(usage.get("total_tokens"))
        return TokenUsage(prompt, completion, total or sum_tokens(prompt, completion))

    if provider == "claude":
        prompt = int_or_none(usage.get("input_tokens"))
        completion = int_or_none(usage.get("output_tokens"))
        return TokenUsage(prompt, completion, sum_tokens(prompt, completion))

    prompt = int_or_none(usage.get("prompt_tokens"))
    completion = int_or_none(usage.get("completion_tokens"))
    total = int_or_none(usage.get("total_tokens"))
    return TokenUsage(prompt, completion, total or sum_tokens(prompt, completion))


def int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    return int(value)


def sum_tokens(prompt_tokens: int | None, completion_tokens: int | None) -> int | None:
    if prompt_tokens is None and completion_tokens is None:
        return None
    return (prompt_tokens or 0) + (completion_tokens or 0)
