from __future__ import annotations

import os

from backend.auth.accounts import PostgresUserAccountRepository
from backend.org_sync.client import HttpxDingtalkClient
from backend.org_sync.sync import sync_organization
from backend.storage.department import PostgresDepartmentRepository


def main() -> None:
    """跑一次钉钉组织同步：钉钉 → 平台库（部门 / 账号 / 人↔部门）。

    需要环境变量：DATABASE_URL、DINGTALK_CLIENT_ID、DINGTALK_CLIENT_SECRET。
    凭据走环境变量、不硬编码（决策 #34 密钥纪律）。
    """
    database_url = os.environ.get("DATABASE_URL")
    client_id = os.environ.get("DINGTALK_CLIENT_ID")
    client_secret = os.environ.get("DINGTALK_CLIENT_SECRET")
    missing = [
        name
        for name, value in (
            ("DATABASE_URL", database_url),
            ("DINGTALK_CLIENT_ID", client_id),
            ("DINGTALK_CLIENT_SECRET", client_secret),
        )
        if not value
    ]
    if missing:
        raise SystemExit(f"缺少环境变量：{', '.join(missing)}")
    assert database_url and client_id and client_secret  # for type-narrowing

    client = HttpxDingtalkClient(client_id=client_id, client_secret=client_secret)
    departments = PostgresDepartmentRepository(database_url)
    accounts = PostgresUserAccountRepository(database_url)

    summary = sync_organization(client, departments, accounts)
    print(f"组织同步完成：部门 {summary.department_count} 个，人员 {summary.user_count} 人。")


if __name__ == "__main__":
    main()
