from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from psycopg.rows import dict_row

from backend.storage.db import connect as db_connect

DataLevel = Literal["full", "partial", "minimal"]
CollectMethod = Literal["report", "relay", "key"]

# tool_id 命名规则（SSOT）：`<team>-<tool>` 全小写 kebab，至少两段，
# 段内 [a-z0-9]+，单连字符相连，无前后缀/双连字符。规范见 platform/docs/registry.md。
# 接入层请求模型用它做 Field(pattern=...) 自动校验（非法格式 → 422）。
TOOL_ID_REGEX = r"^[a-z0-9]+(?:-[a-z0-9]+)+$"


class ToolAlreadyExistsError(Exception):
    """tool_id 已存在：注册表主键冲突。注册是显式动作，重复登记应报错而非静默。"""

    def __init__(self, tool_id: str) -> None:
        super().__init__(f"tool_id already registered: {tool_id}")
        self.tool_id = tool_id


@dataclass(frozen=True)
class ToolRegistration:
    tool_id: str
    name: str
    team_id: str | None
    data_level: DataLevel
    collect_method: CollectMethod
    model_default: str | None


class ToolRegistryRepository(Protocol):
    def register_tool(
        self,
        *,
        tool_id: str,
        name: str,
        team_id: str | None = None,
        data_level: DataLevel = "minimal",
        collect_method: CollectMethod = "report",
        model_default: str | None = None,
    ) -> ToolRegistration:
        """Register one tool_id. Raise ToolAlreadyExistsError if it already exists."""

    def get_tool(self, tool_id: str) -> ToolRegistration | None:
        """Find one tool by tool_id."""


class PostgresToolRegistryRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def register_tool(
        self,
        *,
        tool_id: str,
        name: str,
        team_id: str | None = None,
        data_level: DataLevel = "minimal",
        collect_method: CollectMethod = "report",
        model_default: str | None = None,
    ) -> ToolRegistration:
        params = {
            "tool_id": tool_id,
            "name": name,
            "team_id": team_id,
            "data_level": data_level,
            "collect_method": collect_method,
            "model_default": model_default,
        }
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(INSERT_TOOL_SQL, params)
                row = cursor.fetchone()

        if row is None:
            raise ToolAlreadyExistsError(tool_id)
        return row_to_registration(row)

    def get_tool(self, tool_id: str) -> ToolRegistration | None:
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(SELECT_TOOL_SQL, {"tool_id": tool_id})
                row = cursor.fetchone()

        if row is None:
            return None
        return row_to_registration(row)


def row_to_registration(row: object) -> ToolRegistration:
    if not isinstance(row, dict):
        raise RuntimeError("tool_registry row not found")
    return ToolRegistration(
        tool_id=str(row["tool_id"]),
        name=str(row["name"]),
        team_id=None if row["team_id"] is None else str(row["team_id"]),
        data_level=_as_data_level(row["data_level"]),
        collect_method=_as_collect_method(row["collect_method"]),
        model_default=None if row["model_default"] is None else str(row["model_default"]),
    )


def _as_data_level(value: object) -> DataLevel:
    if value in ("full", "partial", "minimal"):
        return value
    raise RuntimeError(f"unexpected data_level: {value!r}")


def _as_collect_method(value: object) -> CollectMethod:
    if value in ("report", "relay", "key"):
        return value
    raise RuntimeError(f"unexpected collect_method: {value!r}")


INSERT_TOOL_SQL = """
INSERT INTO tool_registry (tool_id, name, team_id, data_level, collect_method, model_default)
VALUES (
    %(tool_id)s, %(name)s, %(team_id)s, %(data_level)s, %(collect_method)s, %(model_default)s
)
ON CONFLICT (tool_id) DO NOTHING
RETURNING tool_id, name, team_id, data_level, collect_method, model_default
"""

SELECT_TOOL_SQL = """
SELECT tool_id, name, team_id, data_level, collect_method, model_default
FROM tool_registry
WHERE tool_id = %(tool_id)s
"""
