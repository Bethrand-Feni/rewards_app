from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

PBKDF2_ITERATIONS = 600_000


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_credential(value: str, pepper: str, salt: str | None = None) -> tuple[str, str]:
    salt_bytes = _unb64(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", f"{value}:{pepper}".encode(), salt_bytes, PBKDF2_ITERATIONS
    )
    return _b64(digest), _b64(salt_bytes)


def verify_credential(value: str, pepper: str, salt: str, expected: str) -> bool:
    actual, _ = hash_credential(value, pepper, salt)
    return hmac.compare_digest(actual, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(claims: dict, secret: str, ttl_seconds: int = 900) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload_data = {**claims, "iat": int(time.time()), "exp": int(time.time()) + ttl_seconds}
    payload = _b64(json.dumps(payload_data, separators=(",", ":")).encode())
    signature = _b64(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str, secret: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        expected = _b64(
            hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        claims = json.loads(_unb64(payload))
        if int(claims["exp"]) <= int(time.time()):
            raise ValueError("Expired token")
        return claims
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid access token") from exc


@dataclass(frozen=True)
class Principal:
    user_id: str
    family_id: str
    role: str
    display_name: str


def new_family_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))

