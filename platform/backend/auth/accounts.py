from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

from psycopg.rows import dict_row

from backend.auth.passwords import hash_password, verify_password
from backend.storage.db import connect as db_connect

Role = Literal["admin", "user"]


@dataclass(frozen=True)
class UserAccount:
    user_id: str
    username: str
    password_hash: str | None  # 钉钉免登账号无密码（决策 #38/P2，密码登录退役）
    team_id: str | None
    role: Role


class UserAccountRepository(Protocol):
    def create_user(
        self,
        *,
        username: str,
        password: str,
        user_id: str | None = None,
        team_id: str | None = None,
        role: Role = "user",
    ) -> UserAccount:
        """Create one user account."""

    def get_by_username(self, username: str) -> UserAccount | None:
        """Find one user account by username."""

    def get_by_user_id(self, user_id: str) -> UserAccount | None:
        """Find one user account by user_id."""


class PostgresUserAccountRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def create_user(
        self,
        *,
        username: str,
        password: str,
        user_id: str | None = None,
        team_id: str | None = None,
        role: Role = "user",
    ) -> UserAccount:
        account = UserAccount(
            user_id=user_id or str(uuid4()),
            username=username,
            password_hash=hash_password(password),
            team_id=team_id,
            role=role,
        )
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_account (user_id, username, password_hash, team_id, role)
                    VALUES (%(user_id)s, %(username)s, %(password_hash)s, %(team_id)s, %(role)s)
                    RETURNING user_id, username, password_hash, team_id, role
                    """,
                    account.__dict__,
                )
                row = cursor.fetchone()

        return row_to_account(row)

    def upsert_dingtalk_user(self, *, dingtalk_userid: str, name: str) -> str:
        params = {
            "user_id": str(uuid4()),
            "username": dingtalk_userid,  # 无密码登录后 username 仅作唯一标识，取 userid
            "dingtalk_userid": dingtalk_userid,
            "display_name": name,
        }
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(UPSERT_DINGTALK_USER_SQL, params)
                row = cursor.fetchone()
        if not isinstance(row, dict):
            raise RuntimeError("upsert_dingtalk_user returned no row")
        return str(row["user_id"])

    def get_by_username(self, username: str) -> UserAccount | None:
        return self._fetch_one("username", username)

    def get_by_user_id(self, user_id: str) -> UserAccount | None:
        return self._fetch_one("user_id", user_id)

    def _fetch_one(self, column: str, value: str) -> UserAccount | None:
        with db_connect(self._database_url) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT user_id, username, password_hash, team_id, role
                    FROM user_account
                    WHERE {column} = %(value)s
                    """,
                    {"value": value},
                )
                row = cursor.fetchone()

        if row is None:
            return None
        return row_to_account(row)


def authenticate(
    repository: UserAccountRepository,
    *,
    username: str,
    password: str,
) -> UserAccount | None:
    account = repository.get_by_username(username)
    if account is None:
        return None
    if account.password_hash is None:
        # 无密码账号（钉钉免登建的）不允许走密码登录（决策 #38/P2）。
        return None
    if not verify_password(password, account.password_hash):
        return None
    return account


def row_to_account(row: object) -> UserAccount:
    if not isinstance(row, dict):
        raise RuntimeError("user_account row not found")
    return UserAccount(
        user_id=str(row["user_id"]),
        username=str(row["username"]),
        password_hash=None if row["password_hash"] is None else str(row["password_hash"]),
        team_id=None if row["team_id"] is None else str(row["team_id"]),
        role="admin" if row["role"] == "admin" else "user",
    )


# 钉钉同步建账号：无密码（P2），按 dingtalk_userid 幂等 upsert（命中部分唯一索引）。
UPSERT_DINGTALK_USER_SQL = """
INSERT INTO user_account (user_id, username, password_hash, dingtalk_userid, display_name, role)
VALUES (%(user_id)s, %(username)s, NULL, %(dingtalk_userid)s, %(display_name)s, 'user')
ON CONFLICT (dingtalk_userid) WHERE dingtalk_userid IS NOT NULL
DO UPDATE SET display_name = EXCLUDED.display_name, updated_at = now()
RETURNING user_id
"""
