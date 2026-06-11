from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal, Protocol

from psycopg.rows import dict_row

from backend.storage.db import connect as db_connect

DataLevel = Literal["full", "partial", "minimal"]
CollectMethod = Literal["report", "relay", "key"]

# tool_id 命名规则（SSOT）：`<team>-<tool>` 全小写 kebab，至少两段，
# 段内 [a-z0-9]+，单连字符相连，无前后缀/双连字符。规范见 platform/docs/registry-工具注册表.md。
# 接入层请求模型用它做 Field(pattern=...) 自动校验（非法格式 → 422）。
TOOL_ID_REGEX = r"^[a-z0-9]+(?:-[a-z0-9]+)+$"
_TOOL_ID_PATTERN = re.compile(TOOL_ID_REGEX)
CONFIG_FILENAME = "tool.toml"


class ToolConfigError(Exception):
    """Raised when an integrations/<tool_id>/tool.toml file is invalid."""

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


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


@dataclass(frozen=True)
class ToolConfig:
    tool_id: str
    name: str
    team_id: str | None = None
    data_level: DataLevel = "minimal"
    collect_method: CollectMethod = "report"
    model_default: str | None = None
    category: str | None = None
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    thumbnail: str | None = None
    launch_url: str | None = None
    sort_weight: int = 0
    enabled: bool = True


_ALLOWED_CONFIG_KEYS = frozenset(f.name for f in fields(ToolConfig))


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


class ToolDirectory(Protocol):
    def list_enabled_tools(self) -> list[ToolConfig]:
        """Return enabled portal tools ordered for display."""


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


class PostgresToolDirectory:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def list_enabled_tools(self) -> list[ToolConfig]:
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(LIST_ENABLED_TOOLS_SQL)
                rows = cursor.fetchall()
        return [row_to_config(row) for row in rows]


def discover_tool_configs(integrations_dir: Path) -> list[Path]:
    return sorted(integrations_dir.glob(f"*/{CONFIG_FILENAME}"))


def load_tool_configs(integrations_dir: Path) -> list[ToolConfig]:
    return [parse_tool_config(path) for path in discover_tool_configs(integrations_dir)]


def parse_tool_config(path: Path) -> ToolConfig:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ToolConfigError(path, f"TOML syntax error: {exc}") from exc

    unknown = sorted(set(raw) - _ALLOWED_CONFIG_KEYS)
    if unknown:
        raise ToolConfigError(path, f"unknown fields: {unknown}")

    tool_id = _required_str(path, raw, "tool_id")
    if _TOOL_ID_PATTERN.fullmatch(tool_id) is None:
        raise ToolConfigError(path, f"tool_id does not match {TOOL_ID_REGEX}: {tool_id!r}")
    if path.parent.name != tool_id:
        raise ToolConfigError(path, f"directory name must equal tool_id {tool_id!r}")

    sort_weight = raw.get("sort_weight", 0)
    if isinstance(sort_weight, bool) or not isinstance(sort_weight, int):
        raise ToolConfigError(path, f"sort_weight must be an integer: {sort_weight!r}")
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ToolConfigError(path, f"enabled must be boolean: {enabled!r}")

    return ToolConfig(
        tool_id=tool_id,
        name=_required_str(path, raw, "name"),
        team_id=_optional_str(path, raw, "team_id"),
        data_level=_as_config_data_level(path, raw.get("data_level", "minimal")),
        collect_method=_as_config_collect_method(path, raw.get("collect_method", "report")),
        model_default=_optional_str(path, raw, "model_default"),
        category=_optional_str(path, raw, "category"),
        display_name=_optional_str(path, raw, "display_name"),
        description=_optional_str(path, raw, "description"),
        icon=_optional_str(path, raw, "icon"),
        thumbnail=_optional_str(path, raw, "thumbnail"),
        launch_url=_optional_str(path, raw, "launch_url"),
        sort_weight=sort_weight,
        enabled=enabled,
    )


def apply_configs(database_url: str, configs: list[ToolConfig]) -> list[str]:
    with db_connect(database_url) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                for config in configs:
                    cursor.execute(UPSERT_TOOL_SQL, _upsert_params(config))
    return [config.tool_id for config in configs]


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


def row_to_config(row: object) -> ToolConfig:
    if not isinstance(row, dict):
        raise RuntimeError("tool_registry row not found")
    return ToolConfig(
        tool_id=str(row["tool_id"]),
        name=str(row["name"]),
        team_id=None if row["team_id"] is None else str(row["team_id"]),
        data_level=_as_data_level(row["data_level"]),
        collect_method=_as_collect_method(row["collect_method"]),
        model_default=None if row["model_default"] is None else str(row["model_default"]),
        category=None if row["category"] is None else str(row["category"]),
        display_name=None if row["display_name"] is None else str(row["display_name"]),
        description=None if row["description"] is None else str(row["description"]),
        icon=None if row["icon"] is None else str(row["icon"]),
        thumbnail=None if row["thumbnail"] is None else str(row["thumbnail"]),
        launch_url=None if row["launch_url"] is None else str(row["launch_url"]),
        sort_weight=int(row["sort_weight"]),
        enabled=bool(row["enabled"]),
    )


def _required_str(path: Path, raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolConfigError(path, f"{key} is required and must be a non-empty string")
    return value


def _optional_str(path: Path, raw: dict[str, object], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ToolConfigError(path, f"{key} must be a non-empty string when provided")
    return value


def _as_config_data_level(path: Path, value: object) -> DataLevel:
    if value in ("full", "partial", "minimal"):
        return value
    raise ToolConfigError(path, f"data_level must be full, partial, or minimal: {value!r}")


def _as_config_collect_method(path: Path, value: object) -> CollectMethod:
    if value in ("report", "relay", "key"):
        return value
    raise ToolConfigError(path, f"collect_method must be report, relay, or key: {value!r}")


def _upsert_params(config: ToolConfig) -> dict[str, object | None]:
    return {f.name: getattr(config, f.name) for f in fields(ToolConfig)}


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

LIST_ENABLED_TOOLS_SQL = """
SELECT tool_id, name, team_id, data_level, collect_method, model_default,
       category, display_name, description, icon, thumbnail, launch_url,
       sort_weight, enabled
FROM tool_registry
WHERE enabled
ORDER BY sort_weight DESC, tool_id
"""

UPSERT_TOOL_SQL = """
INSERT INTO tool_registry (
    tool_id, name, team_id, data_level, collect_method, model_default,
    category, display_name, description, icon, thumbnail, launch_url,
    sort_weight, enabled
) VALUES (
    %(tool_id)s, %(name)s, %(team_id)s, %(data_level)s, %(collect_method)s, %(model_default)s,
    %(category)s, %(display_name)s, %(description)s, %(icon)s, %(thumbnail)s, %(launch_url)s,
    %(sort_weight)s, %(enabled)s
)
ON CONFLICT (tool_id) DO UPDATE SET
    name = EXCLUDED.name,
    team_id = EXCLUDED.team_id,
    data_level = EXCLUDED.data_level,
    collect_method = EXCLUDED.collect_method,
    model_default = EXCLUDED.model_default,
    category = EXCLUDED.category,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    icon = EXCLUDED.icon,
    thumbnail = EXCLUDED.thumbnail,
    launch_url = EXCLUDED.launch_url,
    sort_weight = EXCLUDED.sort_weight,
    enabled = EXCLUDED.enabled,
    updated_at = now()
"""
