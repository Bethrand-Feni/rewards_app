import time

import pytest

from app.security import (
    create_access_token,
    decode_access_token,
    hash_credential,
    verify_credential,
)


def test_credentials_are_salted_and_verifiable():
    first, first_salt = hash_credential("123456", "pepper")
    second, second_salt = hash_credential("123456", "pepper")
    assert first != second
    assert first_salt != second_salt
    assert verify_credential("123456", "pepper", first_salt, first)
    assert not verify_credential("123455", "pepper", first_salt, first)


def test_access_token_round_trip():
    token = create_access_token({"sub": "u1", "family_id": "f1", "role": "CHILD"}, "secret")
    claims = decode_access_token(token, "secret")
    assert claims["sub"] == "u1"
    assert claims["family_id"] == "f1"


def test_access_token_rejects_wrong_secret():
    token = create_access_token({"sub": "u1"}, "secret")
    with pytest.raises(ValueError):
        decode_access_token(token, "different")


def test_access_token_rejects_expiry():
    token = create_access_token({"sub": "u1"}, "secret", ttl_seconds=-1)
    time.sleep(0.01)
    with pytest.raises(ValueError):
        decode_access_token(token, "secret")

