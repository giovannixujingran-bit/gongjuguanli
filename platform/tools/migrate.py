from __future__ import annotations

import argparse
import os
from pathlib import Path

from backend.storage.migrate import apply_pending

# 迁移文件默认位置：建表 SQL 所在目录（0001_init.sql 等）。
_PLATFORM_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MIGRATIONS_DIR = _PLATFORM_ROOT / "backend" / "storage" / "migrations"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="按顺序、幂等地把待办的建表/改表 SQL 应用到数据库（迁移执行器）。"
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="目标 PostgreSQL 连接串；默认取环境变量 DATABASE_URL。",
    )
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=DEFAULT_MIGRATIONS_DIR,
        help="迁移文件目录；默认 backend/storage/migrations。",
    )
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required（用 --database-url 或环境变量提供）。")

    applied = apply_pending(args.database_url, args.migrations_dir)

    if not applied:
        print("已是最新：没有待办的迁移。")
        return
    print(f"已应用 {len(applied)} 个迁移：")
    for migration in applied:
        print(f"  - {migration.name}")


if __name__ == "__main__":
    main()
