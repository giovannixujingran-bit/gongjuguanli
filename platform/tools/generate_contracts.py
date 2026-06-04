from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "shared" / "schema" / "event.schema.json"
OUT_DIR = ROOT / "shared" / "contracts"


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    properties: dict[str, dict[str, Any]] = schema["properties"]
    required = set(schema.get("required", []))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "event_model.py").write_text(
        render_pydantic_model(properties, required),
        encoding="utf-8",
        newline="\n",
    )
    (OUT_DIR / "event.d.ts").write_text(
        render_typescript_model(properties, required),
        encoding="utf-8",
        newline="\n",
    )
    print("生成完成：shared/contracts/event_model.py, shared/contracts/event.d.ts")


def render_pydantic_model(properties: dict[str, dict[str, Any]], required: set[str]) -> str:
    lines = [
        (
            "# 自动生成，勿手改 —— 由 tools/generate_contracts.py "
            "从 shared/schema/event.schema.json 生成"
        ),
        "from __future__ import annotations",
        "",
        "from datetime import datetime",
        "from decimal import Decimal",
        "from typing import Any, Literal",
        "from uuid import UUID",
        "",
        "from pydantic import BaseModel, ConfigDict, Field",
        "",
        "",
        "class UsageEvent(BaseModel):",
        '    """统一事件记录。字段定义来自 shared/schema/event.schema.json。"""',
        "",
        '    model_config = ConfigDict(extra="forbid")',
        "",
    ]

    for name, definition in properties.items():
        annotation = python_type(name, definition)
        default = "..." if name in required else "None"
        constraints = field_constraints(definition)
        if constraints:
            lines.append(f"    {name}: {annotation} = Field({default}, {constraints})")
        elif name in required:
            # 必填且无额外约束：用 Field(...) 而非裸 ...，否则 mypy strict 把
            # Ellipsis 当作与字段类型不兼容的赋值而报错（运行时两者等价）。
            lines.append(f"    {name}: {annotation} = Field(...)")
        else:
            lines.append(f"    {name}: {annotation} = {default}")

    lines.append("")
    return "\n".join(lines)


def python_type(name: str, definition: dict[str, Any]) -> str:
    if "enum" in definition:
        values = [item for item in definition["enum"] if item is not None]
        literal = "Literal[" + ", ".join(repr(item) for item in values) + "]"
        return f"{literal} | None" if None in definition["enum"] else literal

    type_names = schema_type_names(definition)
    nullable = "null" in type_names
    non_null_type = next((item for item in type_names if item != "null"), None)

    if definition.get("format") == "uuid":
        base = "UUID"
    elif definition.get("format") == "date-time":
        base = "datetime"
    elif name == "cost":
        base = "Decimal"
    elif name == "result_quality":
        base = "float | str"
    elif non_null_type == "string":
        base = "str"
    elif non_null_type == "integer":
        base = "int"
    elif non_null_type == "number":
        base = "float"
    elif non_null_type == "boolean":
        base = "bool"
    elif non_null_type == "object":
        base = "dict[str, Any]"
    else:
        base = "Any"

    return f"{base} | None" if nullable else base


def field_constraints(definition: dict[str, Any]) -> str:
    constraints: list[str] = []
    if "minimum" in definition:
        constraints.append(f"ge={definition['minimum']}")
    if "minLength" in definition:
        constraints.append(f"min_length={definition['minLength']}")
    if "pattern" in definition:
        constraints.append(f"pattern={definition['pattern']!r}")
    return ", ".join(constraints)


def render_typescript_model(properties: dict[str, dict[str, Any]], required: set[str]) -> str:
    lines = [
        (
            "// 自动生成，勿手改 —— 由 tools/generate_contracts.py "
            "从 shared/schema/event.schema.json 生成"
        ),
        "export interface UsageEvent {",
    ]
    for name, definition in properties.items():
        optional = "" if name in required else "?"
        lines.append(f"  {name}{optional}: {typescript_type(definition)};")
    lines.extend(["}", ""])
    return "\n".join(lines)


def typescript_type(definition: dict[str, Any]) -> str:
    if "enum" in definition:
        return " | ".join(
            "null" if item is None else json.dumps(item) for item in definition["enum"]
        )

    type_names = schema_type_names(definition)
    return " | ".join(ts_scalar_type(type_name) for type_name in type_names)


def schema_type_names(definition: dict[str, Any]) -> list[str]:
    schema_type = definition.get("type")
    if isinstance(schema_type, list):
        return [item for item in schema_type if isinstance(item, str)]
    if isinstance(schema_type, str):
        return [schema_type]
    return []


def ts_scalar_type(type_name: str | None) -> str:
    if type_name == "string":
        return "string"
    if type_name in {"integer", "number"}:
        return "number"
    if type_name == "boolean":
        return "boolean"
    if type_name == "object":
        return "Record<string, unknown>"
    if type_name == "null":
        return "null"
    return "unknown"


if __name__ == "__main__":
    main()
