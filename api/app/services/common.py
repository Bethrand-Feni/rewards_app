from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return str(uuid4())


def env_value(env: Any, name: str, default: str = "") -> str:
    value = getattr(env, name, default)
    return str(value) if value is not None else default
