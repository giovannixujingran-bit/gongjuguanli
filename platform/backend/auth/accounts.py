from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from backend.auth.passwords import hash_password, verify_password

Role = Literal["admin", "user"]


@dataclass(frozen=True)
class UserAccount:
    user_id: str
    username: str
    password_hash: str
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
        with psycopg.connect(self._database_url) as connection:
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

    def get_by_username(self, username: str) -> UserAccount | None:
        return self._fetch_one("username", username)

    def get_by_user_id(self, user_id: str) -> UserAccount | None:
        return self._fetch_one("user_id", user_id)

    def _fetch_one(self, column: str, value: str) -> UserAccount | None:
        with psycopg.connect(self._database_url) as connection:
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
    if not verify_password(password, account.password_hash):
        return None
    return account


def row_to_account(row: object) -> UserAccount:
    if not isinstance(row, dict):
        raise RuntimeError("user_account row not found")
    return UserAccount(
        user_id=str(row["user_id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        team_id=None if row["team_id"] is None else str(row["team_id"]),
        role="admin" if row["role"] == "admin" else "user",
    )
