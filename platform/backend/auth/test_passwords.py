from __future__ import annotations

from backend.auth.passwords import hash_password, verify_password


def test_hash_password_verifies_original_password() -> None:
    password_hash = hash_password("secret")

    assert verify_password("secret", password_hash)
    assert not verify_password("wrong", password_hash)
    assert "secret" not in password_hash


def test_verify_password_rejects_malformed_hash() -> None:
    assert not verify_password("secret", "not-a-valid-hash")
