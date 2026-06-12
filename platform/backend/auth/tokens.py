from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from backend.auth.accounts import UserAccount

DEFAULT_TOKEN_TTL_SECONDS = 3600


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    username: str
    role: str
    team_id: str | None
    is_superadmin: bool
    expires_at: int


def issue_token(
    account: UserAccount,
    *,
    secret: str,
    is_superadmin: bool = False,
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
) -> tuple[str, int]:
    expires_at = int(time.time()) + ttl_seconds
    claims = TokenClaims(
        user_id=account.user_id,
        username=account.username,
        role=account.role,
        team_id=account.team_id,
        is_superadmin=is_superadmin,
        expires_at=expires_at,
    )
    payload = encode_json(claims.__dict__)
    signature = sign(payload, secret)
    return f"{payload}.{signature}", expires_at


def verify_token(token: str, *, secret: str) -> TokenClaims | None:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None

    if not hmac.compare_digest(sign(payload, secret), signature):
        return None

    data = decode_json(payload)
    if int(data.get("expires_at", 0)) < int(time.time()):
        return None

    return TokenClaims(
        user_id=str(data["user_id"]),
        username=str(data["username"]),
        role=str(data["role"]),
        team_id=None if data.get("team_id") is None else str(data["team_id"]),
        is_superadmin=bool(data.get("is_superadmin", False)),
        expires_at=int(data["expires_at"]),
    )


def bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    return authorization[len(prefix) :].strip() or None


def encode_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_json(value: str) -> dict[str, Any]:
    padded = value + "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("token payload must be an object")
    return decoded


def sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
