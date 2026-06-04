from __future__ import annotations

from backend.auth.accounts import UserAccount
from backend.auth.tokens import bearer_token, issue_token, verify_token


def test_issue_and_verify_token() -> None:
    account = UserAccount(
        user_id="user-001",
        username="alice",
        password_hash="hidden",
        team_id="team-a",
        role="user",
    )

    token, expires_at = issue_token(account, secret="secret")
    claims = verify_token(token, secret="secret")

    assert claims is not None
    assert claims.user_id == "user-001"
    assert claims.username == "alice"
    assert claims.team_id == "team-a"
    assert claims.expires_at == expires_at
    assert verify_token(token, secret="wrong") is None


def test_bearer_token_parsing() -> None:
    assert bearer_token("Bearer abc") == "abc"
    assert bearer_token("Basic abc") is None
    assert bearer_token(None) is None
