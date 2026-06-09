from __future__ import annotations

from backend.storage.db import connect as db_connect


class PostgresDepartmentRepository:
    """部门 + 人↔部门的落库实现（满足 org_sync.DepartmentWriter 协议）。

    只收基本类型，不 import 上层 org_sync（守单向分层）。
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def upsert_department(self, *, dept_id: int, name: str, parent_id: int | None) -> None:
        with db_connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    UPSERT_DEPARTMENT_SQL,
                    {"dept_id": dept_id, "name": name, "parent_id": parent_id},
                )

    def deactivate_missing(self, active_dept_ids: set[int]) -> None:
        # 本轮没见到的钉钉部门 → 软删（active=false），不硬删（决策 #38/P6）。
        with db_connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    DEACTIVATE_MISSING_SQL,
                    {"active_ids": list(active_dept_ids)},
                )

    def set_user_departments(self, *, user_id: str, dept_ids: list[int]) -> None:
        # 按钉钉归属整体覆盖：先清该人的旧归属，再插新归属（同一事务）。
        with db_connect(self._database_url) as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(DELETE_USER_DEPARTMENTS_SQL, {"user_id": user_id})
                    for dept_id in dept_ids:
                        cursor.execute(
                            INSERT_USER_DEPARTMENT_SQL,
                            {"user_id": user_id, "dept_id": dept_id},
                        )


UPSERT_DEPARTMENT_SQL = """
INSERT INTO department (dept_id, parent_id, name, source, active, synced_at)
VALUES (%(dept_id)s, %(parent_id)s, %(name)s, 'dingtalk', TRUE, now())
ON CONFLICT (dept_id) DO UPDATE SET
    parent_id = EXCLUDED.parent_id,
    name      = EXCLUDED.name,
    active    = TRUE,
    synced_at = now()
"""

DEACTIVATE_MISSING_SQL = """
UPDATE department
SET active = FALSE
WHERE source = 'dingtalk'
  AND active = TRUE
  AND dept_id <> ALL(%(active_ids)s)
"""

DELETE_USER_DEPARTMENTS_SQL = """
DELETE FROM user_department WHERE user_id = %(user_id)s
"""

INSERT_USER_DEPARTMENT_SQL = """
INSERT INTO user_department (user_id, dept_id, is_primary)
VALUES (%(user_id)s, %(dept_id)s, FALSE)
ON CONFLICT (user_id, dept_id) DO NOTHING
"""
