from __future__ import annotations

from pathlib import Path

import pytest

from backend.storage.migrate import (
    discover_migrations,
    parse_migration_version,
    pending_migrations,
)


def _write(directory: Path, name: str, body: str = "SELECT 1;") -> None:
    (directory / name).write_text(body, encoding="utf-8")


def test_parse_migration_version_reads_numeric_prefix() -> None:
    assert parse_migration_version("0001_init.sql") == 1
    assert parse_migration_version("0012_add_cost_column.sql") == 12


def test_parse_migration_version_ignores_non_migration_files() -> None:
    # 不是 NNNN_*.sql 形态的，一律不当作迁移（README、无编号、非 sql）。
    assert parse_migration_version("README.md") is None
    assert parse_migration_version("notes.sql") is None
    assert parse_migration_version("init.sql") is None


def test_discover_migrations_sorts_numerically_and_skips_non_sql(tmp_path: Path) -> None:
    _write(tmp_path, "0002_b.sql")
    _write(tmp_path, "0010_c.sql")
    _write(tmp_path, "0001_a.sql")
    _write(tmp_path, "README.md")

    found = discover_migrations(tmp_path)

    # 按数字而非字符串排序：10 必须排在 2 之后。
    assert [m.version for m in found] == [1, 2, 10]
    assert [m.name for m in found] == ["0001_a", "0002_b", "0010_c"]


def test_discover_migrations_rejects_duplicate_version(tmp_path: Path) -> None:
    _write(tmp_path, "0001_a.sql")
    _write(tmp_path, "0001_b.sql")

    with pytest.raises(ValueError):
        discover_migrations(tmp_path)


def test_pending_migrations_filters_already_applied(tmp_path: Path) -> None:
    _write(tmp_path, "0001_a.sql")
    _write(tmp_path, "0002_b.sql")
    _write(tmp_path, "0003_c.sql")
    found = discover_migrations(tmp_path)

    pending = pending_migrations(found, applied={1, 2})

    assert [m.version for m in pending] == [3]


def test_pending_migrations_empty_when_all_applied(tmp_path: Path) -> None:
    _write(tmp_path, "0001_a.sql")
    found = discover_migrations(tmp_path)

    assert pending_migrations(found, applied={1}) == []
