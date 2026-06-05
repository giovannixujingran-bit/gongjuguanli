from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from psycopg import Connection
from psycopg.rows import TupleRow

from backend.storage.db import connect as db_connect

# 迁移文件命名：四位（或更多）数字编号 + 下划线 + 描述 + .sql，例如 0001_init.sql。
# 编号决定执行顺序；README.md、无编号 .sql 等都不算迁移。
_MIGRATION_FILENAME = re.compile(r"^(\d+)_.+\.sql$")

# 跟踪表：记"哪些便利贴办过了"。每办成一张就插一行，靠它实现"不重复办"。
_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER     PRIMARY KEY,
    name        TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


@dataclass(frozen=True)
class Migration:
    """一份迁移文件 = 一张"待办便利贴"。"""

    version: int
    name: str  # 文件名去掉 .sql，例如 "0001_init"
    path: Path


def parse_migration_version(filename: str) -> int | None:
    """从文件名解析迁移编号；不是迁移文件则返回 None。"""
    match = _MIGRATION_FILENAME.match(filename)
    if match is None:
        return None
    return int(match.group(1))


def discover_migrations(migrations_dir: Path) -> list[Migration]:
    """扫描目录里所有迁移文件，按编号升序返回。

    编号重复会抛 ValueError——否则"先办哪张"有歧义，必须当场拦住。
    """
    found: dict[int, Migration] = {}
    for path in migrations_dir.iterdir():
        version = parse_migration_version(path.name)
        if version is None:
            continue
        if version in found:
            raise ValueError(
                f"duplicate migration version {version}: {found[version].path.name} 与 {path.name}"
            )
        found[version] = Migration(version=version, name=path.stem, path=path)
    return [found[version] for version in sorted(found)]


def pending_migrations(migrations: list[Migration], applied: set[int]) -> list[Migration]:
    """从全部迁移里挑出还没办过的（编号不在 applied 集合中），保持顺序。"""
    return [m for m in migrations if m.version not in applied]


# --- 下面是动数据库的薄层（IO）。决策逻辑都在上面的纯函数里，已被单测覆盖；
# --- 这层只负责"连库 + 读已办 + 逐张办"，按本项目惯例靠真实库集成验证（见 docs/smoke.md）。


def read_applied_versions(connection: Connection[TupleRow]) -> set[int]:
    """读跟踪表里已办过的编号集合；表不存在则先建。"""
    with connection.cursor() as cursor:
        cursor.execute(_MIGRATIONS_TABLE_SQL)
        cursor.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cursor.fetchall()}


def apply_pending(database_url: str, migrations_dir: Path) -> list[Migration]:
    """把所有还没办的迁移按编号顺序办掉，返回本次实际办了哪些。

    幂等：已办过的跳过。每张迁移连同它的"已办登记"放在同一个事务里——
    要么整张生效并记账，要么整张回滚，不会出现"SQL 跑了一半却没登记"的半生效状态。
    """
    with db_connect(database_url) as connection:
        applied = read_applied_versions(connection)
        todo = pending_migrations(discover_migrations(migrations_dir), applied)
        for migration in todo:
            sql = migration.path.read_text(encoding="utf-8")
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    cursor.execute(
                        "INSERT INTO schema_migrations (version, name) "
                        "VALUES (%(version)s, %(name)s)",
                        {"version": migration.version, "name": migration.name},
                    )
        return todo
