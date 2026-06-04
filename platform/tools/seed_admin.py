"""引导首个管理员账号。

`/auth/users` 端点要求调用者本身是 admin（防止任何人在局域网内给自己开 admin），
所以「第一个 admin」无法经端点创建——由运维用 DB 凭据离线跑本脚本引导一次。
之后所有账号都由 admin 登录后经 `/auth/users` 创建。

用法（在 platform 目录下）：

    python tools/seed_admin.py --username alice --password "<set-a-strong-one>"

或用环境变量 SEED_ADMIN_USERNAME / SEED_ADMIN_PASSWORD。DATABASE_URL 必填。
"""

from __future__ import annotations

import argparse
import os

from backend.auth.accounts import PostgresUserAccountRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the first admin account.")
    parser.add_argument("--username", default=os.environ.get("SEED_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("SEED_ADMIN_PASSWORD"))
    parser.add_argument("--team-id", default=os.environ.get("SEED_ADMIN_TEAM_ID"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required.")
    if not args.username or not args.password:
        raise SystemExit("--username and --password (or SEED_ADMIN_* env) are required.")

    repository = PostgresUserAccountRepository(args.database_url)
    account = repository.create_user(
        username=args.username,
        password=args.password,
        team_id=args.team_id,
        role="admin",
    )
    print(f"created admin: user_id={account.user_id} username={account.username}")


if __name__ == "__main__":
    main()
