from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

import asgi
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from workers import WorkerEntrypoint

try:
    from models import (
        AdjustmentCreate,
        ChildCreate,
        ChildLogin,
        ChoreWrite,
        ParentLogin,
        ParentRegister,
        PinReset,
        RedemptionReview,
        RefreshRequest,
        ReviewComment,
        ReviewSubmission,
        RewardWrite,
    )
    from security import (
        Principal,
        create_access_token,
        decode_access_token,
        hash_credential,
        hash_token,
        new_family_code,
        verify_credential,
    )
except ImportError:
    # CPython tests import this file through the local ``app`` package, while
    # Workers uploads sibling modules at the bundle root.
    from app.models import (
        AdjustmentCreate,
        ChildCreate,
        ChildLogin,
        ChoreWrite,
        ParentLogin,
        ParentRegister,
        PinReset,
        RedemptionReview,
        RefreshRequest,
        ReviewComment,
        ReviewSubmission,
        RewardWrite,
    )
    from app.security import (
        Principal,
        create_access_token,
        decode_access_token,
        hash_credential,
        hash_token,
        new_family_code,
        verify_credential,
    )

MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ACTIVE_SUBMISSION_STATUSES = ("PENDING", "CHANGES_REQUESTED")

app = FastAPI(title="Sibling Rewards API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await asgi.fetch(app, request, self.env)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return str(uuid4())


def env_for(request: Request):
    return request.scope["env"]


def env_value(env: Any, name: str, default: str = "") -> str:
    value = getattr(env, name, default)
    return str(value) if value is not None else default


def to_python(value: Any) -> Any:
    if hasattr(value, "to_py"):
        return value.to_py()
    return value


async def rows(env: Any, sql: str, *params: Any) -> list[dict]:
    result = await env.DB.prepare(sql).bind(*params).all()
    return list(to_python(result.results))


async def row(env: Any, sql: str, *params: Any) -> dict | None:
    result = await env.DB.prepare(sql).bind(*params).first()
    converted = to_python(result)
    return dict(converted) if converted else None


async def run(env: Any, sql: str, *params: Any) -> int:
    result = await env.DB.prepare(sql).bind(*params).run()
    meta = to_python(result.meta)
    return int(meta.get("changes", 0))


async def batch(env: Any, statements: list[Any]) -> list[Any]:
    return list(to_python(await env.DB.batch(statements)))


def auth_error(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


async def current_principal(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise auth_error()
    env = env_for(request)
    try:
        claims = decode_access_token(
            authorization.removeprefix("Bearer ").strip(), env_value(env, "JWT_SECRET")
        )
    except ValueError as exc:
        raise auth_error("Session expired or invalid") from exc
    account = await row(
        env,
        """
        SELECT u.id AS user_id, u.display_name, fm.family_id, fm.role
        FROM users u
        JOIN family_members fm ON fm.user_id = u.id
        WHERE u.id = ? AND fm.family_id = ? AND u.is_active = 1
        """,
        claims.get("sub"),
        claims.get("family_id"),
    )
    if not account:
        raise auth_error("Account is unavailable")
    return Principal(**account)


PrincipalDep = Annotated[Principal, Depends(current_principal)]


def require_role(principal: Principal, role: str) -> None:
    if principal.role != role:
        raise HTTPException(status_code=403, detail=f"{role.title()} access required")


async def issue_session(env: Any, account: dict) -> dict:
    now = datetime.now(UTC)
    refresh = secrets.token_urlsafe(48)
    await run(
        env,
        """
        INSERT INTO auth_sessions
        (id, user_id, refresh_token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        new_id(),
        account["user_id"],
        hash_token(refresh),
        (now + timedelta(days=30)).isoformat(),
        now.isoformat(),
    )
    claims = {
        "sub": account["user_id"],
        "family_id": account["family_id"],
        "role": account["role"],
    }
    return {
        "access_token": create_access_token(claims, env_value(env, "JWT_SECRET")),
        "refresh_token": refresh,
        "expires_in": 900,
        "user": account,
    }


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def identity_hash(value: str, env: Any) -> str:
    return hash_token(f"{value.casefold()}:{env_value(env, 'CREDENTIAL_PEPPER')}")


async def check_login_lock(env: Any, identity: str) -> None:
    attempt = await row(
        env, "SELECT attempts, locked_until FROM login_attempts WHERE identity_hash = ?", identity
    )
    if attempt and attempt["locked_until"] and attempt["locked_until"] > utc_now():
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in 15 minutes.")


async def failed_login(env: Any, identity: str) -> None:
    now = datetime.now(UTC)
    current = await row(
        env, "SELECT attempts FROM login_attempts WHERE identity_hash = ?", identity
    )
    attempts = int(current["attempts"]) + 1 if current else 1
    locked_until = (now + timedelta(minutes=15)).isoformat() if attempts >= 5 else None
    await run(
        env,
        """
        INSERT INTO login_attempts(identity_hash, attempts, locked_until, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(identity_hash) DO UPDATE SET
          attempts = excluded.attempts,
          locked_until = excluded.locked_until,
          updated_at = excluded.updated_at
        """,
        identity,
        attempts,
        locked_until,
        now.isoformat(),
    )


async def clear_login_attempts(env: Any, identity: str) -> None:
    await run(env, "DELETE FROM login_attempts WHERE identity_hash = ?", identity)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sibling-rewards-api"}


@app.post("/api/v1/auth/parent/register", status_code=201)
async def register_parent(payload: ParentRegister, request: Request):
    env = env_for(request)
    email = normalize_email(payload.email)
    if await row(env, "SELECT id FROM users WHERE email = ?", email):
        raise HTTPException(status_code=409, detail="An account already uses this email")
    user_id, family_id, member_id = new_id(), new_id(), new_id()
    password_hash, salt = hash_credential(
        payload.password, env_value(env, "CREDENTIAL_PEPPER")
    )
    now = utc_now()
    code = new_family_code()
    await batch(
        env,
        [
            env.DB.prepare(
                "INSERT INTO families(id, name, access_code, created_at) VALUES (?, ?, ?, ?)"
            ).bind(family_id, payload.family_name.strip(), code, now),
            env.DB.prepare(
                """
                INSERT INTO users
                (id, email, display_name, credential_hash, credential_salt, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """
            ).bind(
                user_id,
                email,
                payload.display_name.strip(),
                password_hash,
                salt,
                now,
                now,
            ),
            env.DB.prepare(
                """
                INSERT INTO family_members(id, family_id, user_id, role, joined_at)
                VALUES (?, ?, ?, 'PARENT', ?)
                """
            ).bind(member_id, family_id, user_id, now),
        ],
    )
    return await issue_session(
        env,
        {
            "user_id": user_id,
            "family_id": family_id,
            "role": "PARENT",
            "display_name": payload.display_name.strip(),
            "family_name": payload.family_name.strip(),
            "family_code": code,
        },
    )


@app.post("/api/v1/auth/parent/login")
async def login_parent(payload: ParentLogin, request: Request):
    env = env_for(request)
    email = normalize_email(payload.email)
    identity = identity_hash(f"parent:{email}", env)
    await check_login_lock(env, identity)
    account = await row(
        env,
        """
        SELECT u.id AS user_id, u.display_name, u.credential_hash, u.credential_salt,
               fm.family_id, fm.role, f.name AS family_name, f.access_code AS family_code
        FROM users u
        JOIN family_members fm ON fm.user_id = u.id
        JOIN families f ON f.id = fm.family_id
        WHERE u.email = ? AND u.is_active = 1 AND fm.role = 'PARENT'
        """,
        email,
    )
    valid = account and verify_credential(
        payload.password,
        env_value(env, "CREDENTIAL_PEPPER"),
        account["credential_salt"],
        account["credential_hash"],
    )
    if not valid:
        await failed_login(env, identity)
        raise auth_error("Incorrect email or password")
    await clear_login_attempts(env, identity)
    return await issue_session(env, account)


@app.post("/api/v1/auth/child/login")
async def login_child(payload: ChildLogin, request: Request):
    env = env_for(request)
    code = payload.family_code.strip().upper()
    username = normalize_username(payload.username)
    identity = identity_hash(f"child:{code}:{username}", env)
    await check_login_lock(env, identity)
    account = await row(
        env,
        """
        SELECT u.id AS user_id, u.display_name, u.credential_hash, u.credential_salt,
               fm.family_id, fm.role, f.name AS family_name, f.access_code AS family_code
        FROM family_members fm
        JOIN users u ON u.id = fm.user_id
        JOIN families f ON f.id = fm.family_id
        WHERE f.access_code = ? AND fm.username = ? AND fm.role = 'CHILD' AND u.is_active = 1
        """,
        code,
        username,
    )
    valid = account and verify_credential(
        payload.pin,
        env_value(env, "CREDENTIAL_PEPPER"),
        account["credential_salt"],
        account["credential_hash"],
    )
    if not valid:
        await failed_login(env, identity)
        raise auth_error("Incorrect household code, username, or PIN")
    await clear_login_attempts(env, identity)
    return await issue_session(env, account)


@app.post("/api/v1/auth/refresh")
async def refresh_session(payload: RefreshRequest, request: Request):
    env = env_for(request)
    now = utc_now()
    session = await row(
        env,
        """
        SELECT s.id AS session_id, u.id AS user_id, u.display_name,
               fm.family_id, fm.role, f.name AS family_name, f.access_code AS family_code
        FROM auth_sessions s
        JOIN users u ON u.id = s.user_id
        JOIN family_members fm ON fm.user_id = u.id
        JOIN families f ON f.id = fm.family_id
        WHERE s.refresh_token_hash = ? AND s.revoked_at IS NULL
          AND s.expires_at > ? AND u.is_active = 1
        """,
        hash_token(payload.refresh_token),
        now,
    )
    if not session:
        raise auth_error("Refresh session expired or invalid")
    await run(env, "UPDATE auth_sessions SET revoked_at = ? WHERE id = ?", now, session["session_id"])
    return await issue_session(env, session)


@app.post("/api/v1/auth/logout", status_code=204)
async def logout(payload: RefreshRequest, request: Request):
    await run(
        env_for(request),
        "UPDATE auth_sessions SET revoked_at = ? WHERE refresh_token_hash = ?",
        utc_now(),
        hash_token(payload.refresh_token),
    )
    return Response(status_code=204)


@app.get("/api/v1/auth/me")
async def me(principal: PrincipalDep, request: Request):
    family = await row(
        env_for(request), "SELECT name, access_code FROM families WHERE id = ?", principal.family_id
    )
    return {**principal.__dict__, "family_name": family["name"], "family_code": family["access_code"]}


@app.get("/api/v1/household/children")
async def list_children(principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    return await rows(
        env_for(request),
        """
        SELECT u.id, u.display_name, fm.username, u.is_active, u.created_at
        FROM family_members fm JOIN users u ON u.id = fm.user_id
        WHERE fm.family_id = ? AND fm.role = 'CHILD'
        ORDER BY u.display_name COLLATE NOCASE
        """,
        principal.family_id,
    )


@app.post("/api/v1/household/children", status_code=201)
async def create_child(payload: ChildCreate, principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    env = env_for(request)
    username = normalize_username(payload.username)
    exists = await row(
        env,
        "SELECT id FROM family_members WHERE family_id = ? AND username = ?",
        principal.family_id,
        username,
    )
    if exists:
        raise HTTPException(status_code=409, detail="That username is already in use")
    child_id, member_id, now = new_id(), new_id(), utc_now()
    pin_hash, salt = hash_credential(payload.pin, env_value(env, "CREDENTIAL_PEPPER"))
    await batch(
        env,
        [
            env.DB.prepare(
                """
                INSERT INTO users
                (id, display_name, credential_hash, credential_salt, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """
            ).bind(child_id, payload.display_name.strip(), pin_hash, salt, now, now),
            env.DB.prepare(
                """
                INSERT INTO family_members
                (id, family_id, user_id, role, username, joined_at)
                VALUES (?, ?, ?, 'CHILD', ?, ?)
                """
            ).bind(member_id, principal.family_id, child_id, username, now),
        ],
    )
    return {"id": child_id, "display_name": payload.display_name.strip(), "username": username}


@app.post("/api/v1/household/children/{child_id}/reset-pin", status_code=204)
async def reset_child_pin(
    child_id: str, payload: PinReset, principal: PrincipalDep, request: Request
):
    require_role(principal, "PARENT")
    env = env_for(request)
    child = await child_in_family(env, principal.family_id, child_id)
    pin_hash, salt = hash_credential(payload.pin, env_value(env, "CREDENTIAL_PEPPER"))
    await run(
        env,
        "UPDATE users SET credential_hash = ?, credential_salt = ?, updated_at = ? WHERE id = ?",
        pin_hash,
        salt,
        utc_now(),
        child["id"],
    )
    return Response(status_code=204)


@app.patch("/api/v1/household/children/{child_id}/deactivate", status_code=204)
async def deactivate_child(child_id: str, principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    env = env_for(request)
    await child_in_family(env, principal.family_id, child_id)
    now = utc_now()
    await batch(
        env,
        [
            env.DB.prepare("UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?").bind(
                now, child_id
            ),
            env.DB.prepare(
                "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL"
            ).bind(now, child_id),
        ],
    )
    return Response(status_code=204)


@app.post("/api/v1/household/rotate-code")
async def rotate_family_code(principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    env = env_for(request)
    for _ in range(8):
        code = new_family_code()
        try:
            await run(
                env, "UPDATE families SET access_code = ? WHERE id = ?", code, principal.family_id
            )
            return {"family_code": code}
        except Exception:
            continue
    raise HTTPException(status_code=503, detail="Could not generate a household code")


async def child_in_family(env: Any, family_id: str, child_id: str) -> dict:
    child = await row(
        env,
        """
        SELECT u.id, u.display_name FROM users u
        JOIN family_members fm ON fm.user_id = u.id
        WHERE u.id = ? AND fm.family_id = ? AND fm.role = 'CHILD'
        """,
        child_id,
        family_id,
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child profile not found")
    return child


@app.get("/api/v1/chores")
async def list_chores(principal: PrincipalDep, request: Request):
    env = env_for(request)
    if principal.role == "CHILD":
        return await rows(
            env,
            """
            SELECT c.*, u.display_name AS assigned_to_name
            FROM chores c LEFT JOIN users u ON u.id = c.assigned_to_user_id
            WHERE c.family_id = ? AND c.state = 'ACTIVE'
              AND (c.assigned_to_user_id IS NULL OR c.assigned_to_user_id = ?)
            ORDER BY c.created_at DESC
            """,
            principal.family_id,
            principal.user_id,
        )
    return await rows(
        env,
        """
        SELECT c.*, u.display_name AS assigned_to_name
        FROM chores c LEFT JOIN users u ON u.id = c.assigned_to_user_id
        WHERE c.family_id = ? AND c.state != 'INACTIVE'
        ORDER BY c.created_at DESC
        """,
        principal.family_id,
    )


@app.post("/api/v1/chores", status_code=201)
async def create_chore(payload: ChoreWrite, principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    env = env_for(request)
    if payload.assigned_to_user_id:
        await child_in_family(env, principal.family_id, payload.assigned_to_user_id)
    chore_id, now = new_id(), utc_now()
    await run(
        env,
        """
        INSERT INTO chores
        (id, family_id, title, description, suggested_points, mode, assigned_to_user_id,
         created_by_user_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        chore_id,
        principal.family_id,
        payload.title.strip(),
        payload.description.strip(),
        payload.suggested_points,
        payload.mode,
        payload.assigned_to_user_id,
        principal.user_id,
        now,
        now,
    )
    return {"id": chore_id, **payload.model_dump(), "state": "ACTIVE", "created_at": now}


@app.patch("/api/v1/chores/{chore_id}")
async def update_chore(
    chore_id: str, payload: ChoreWrite, principal: PrincipalDep, request: Request
):
    require_role(principal, "PARENT")
    env = env_for(request)
    existing = await resource_in_family(env, "chores", chore_id, principal.family_id)
    if existing["state"] != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active chores can be edited")
    if payload.assigned_to_user_id:
        await child_in_family(env, principal.family_id, payload.assigned_to_user_id)
    await run(
        env,
        """
        UPDATE chores SET title = ?, description = ?, suggested_points = ?, mode = ?,
          assigned_to_user_id = ?, updated_at = ? WHERE id = ?
        """,
        payload.title.strip(),
        payload.description.strip(),
        payload.suggested_points,
        payload.mode,
        payload.assigned_to_user_id,
        utc_now(),
        chore_id,
    )
    return {"id": chore_id, **payload.model_dump(), "state": existing["state"]}


@app.delete("/api/v1/chores/{chore_id}", status_code=204)
async def deactivate_chore(chore_id: str, principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    env = env_for(request)
    await resource_in_family(env, "chores", chore_id, principal.family_id)
    await run(env, "UPDATE chores SET state = 'INACTIVE', updated_at = ? WHERE id = ?", utc_now(), chore_id)
    return Response(status_code=204)


async def resource_in_family(env: Any, table: str, resource_id: str, family_id: str) -> dict:
    if table not in {"chores", "submissions", "rewards", "reward_redemptions"}:
        raise ValueError("Unsupported table")
    result = await row(env, f"SELECT * FROM {table} WHERE id = ? AND family_id = ?", resource_id, family_id)
    if not result:
        raise HTTPException(status_code=404, detail="Resource not found")
    return result


async def validate_image(image: UploadFile) -> bytes:
    if image.content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Use a JPEG, PNG, or WebP image")
    content = await image.read(MAX_IMAGE_BYTES + 1)
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be between 1 byte and 5 MB")
    signatures = (
        content.startswith(b"\xff\xd8\xff"),
        content.startswith(b"\x89PNG\r\n\x1a\n"),
        content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    )
    if not any(signatures):
        raise HTTPException(status_code=415, detail="Image contents do not match a supported format")
    return content


def image_extension(content_type: str) -> str:
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[content_type]


@app.post("/api/v1/submissions", status_code=201)
async def create_submission(
    principal: PrincipalDep,
    request: Request,
    submission_type: Annotated[str, Form()],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    chore_id: Annotated[str | None, Form()] = None,
    image: UploadFile = File(...),
):
    require_role(principal, "CHILD")
    env = env_for(request)
    if submission_type not in {"CHORE", "OTHER_ACTIVITY"}:
        raise HTTPException(status_code=422, detail="Invalid submission type")
    if submission_type == "CHORE" and not chore_id:
        raise HTTPException(status_code=422, detail="A chore is required")
    if submission_type == "OTHER_ACTIVITY" and len(title.strip()) < 2:
        raise HTTPException(status_code=422, detail="Add a title for the activity")
    chore = None
    if chore_id:
        chore = await resource_in_family(env, "chores", chore_id, principal.family_id)
        if chore["state"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="This chore is not available")
        if chore["assigned_to_user_id"] and chore["assigned_to_user_id"] != principal.user_id:
            raise HTTPException(status_code=403, detail="This chore is assigned to someone else")
        existing = await row(
            env,
            """
            SELECT id FROM submissions
            WHERE child_user_id = ? AND chore_id = ? AND status IN ('PENDING', 'CHANGES_REQUESTED')
            """,
            principal.user_id,
            chore_id,
        )
        if existing:
            raise HTTPException(status_code=409, detail="You already have an active submission")
    content = await validate_image(image)
    submission_id, image_id, now = new_id(), new_id(), utc_now()
    object_key = (
        f"families/{principal.family_id}/submissions/{submission_id}/"
        f"{image_id}.{image_extension(image.content_type)}"
    )
    await env.PHOTOS.put(object_key, content)
    try:
        statements = [
            env.DB.prepare(
                """
                INSERT INTO submissions
                (id, family_id, child_user_id, chore_id, submission_type, title, description,
                 status, locks_chore, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?)
                """
            ).bind(
                submission_id,
                principal.family_id,
                principal.user_id,
                chore_id,
                submission_type,
                (chore["title"] if chore else title.strip()),
                description.strip(),
                1 if chore and chore["mode"] == "ONE_TIME" else 0,
                now,
                now,
            ),
            env.DB.prepare(
                """
                INSERT INTO submission_images
                (id, submission_id, revision, r2_object_key, content_type, file_size, created_at)
                VALUES (?, ?, 1, ?, ?, ?, ?)
                """
            ).bind(image_id, submission_id, object_key, image.content_type, len(content), now),
        ]
        if chore and chore["mode"] == "ONE_TIME":
            statements.append(
                env.DB.prepare(
                    "UPDATE chores SET state = 'LOCKED', updated_at = ? WHERE id = ? AND state = 'ACTIVE'"
                ).bind(now, chore_id)
            )
        await batch(env, statements)
    except Exception:
        await env.PHOTOS.delete(object_key)
        raise
    return {"id": submission_id, "status": "PENDING", "created_at": now}


SUBMISSION_SELECT = """
SELECT s.*, u.display_name AS child_name, c.suggested_points, c.mode AS chore_mode,
       si.id AS image_id
FROM submissions s
JOIN users u ON u.id = s.child_user_id
LEFT JOIN chores c ON c.id = s.chore_id
LEFT JOIN submission_images si
  ON si.submission_id = s.id AND si.revision = s.current_revision
"""


@app.get("/api/v1/submissions/mine")
async def my_submissions(principal: PrincipalDep, request: Request):
    require_role(principal, "CHILD")
    return await rows(
        env_for(request),
        SUBMISSION_SELECT + " WHERE s.child_user_id = ? ORDER BY s.created_at DESC LIMIT 50",
        principal.user_id,
    )


@app.get("/api/v1/submissions/pending")
async def pending_submissions(principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    return await rows(
        env_for(request),
        SUBMISSION_SELECT
        + " WHERE s.family_id = ? AND s.status = 'PENDING' ORDER BY s.created_at",
        principal.family_id,
    )


@app.get("/api/v1/submissions/{submission_id}/image")
async def submission_image(submission_id: str, principal: PrincipalDep, request: Request):
    env = env_for(request)
    submission = await resource_in_family(env, "submissions", submission_id, principal.family_id)
    if principal.role == "CHILD" and submission["child_user_id"] != principal.user_id:
        raise HTTPException(status_code=403, detail="This image belongs to another profile")
    image = await row(
        env,
        """
        SELECT r2_object_key, content_type FROM submission_images
        WHERE submission_id = ? AND revision = ?
        """,
        submission_id,
        submission["current_revision"],
    )
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    stored = await env.PHOTOS.get(image["r2_object_key"])
    if not stored:
        raise HTTPException(status_code=404, detail="Image not found")
    buffer = await stored.arrayBuffer()
    content = bytes(to_python(buffer))
    return Response(content=content, media_type=image["content_type"], headers={"Cache-Control": "private, max-age=300"})


@app.post("/api/v1/submissions/{submission_id}/resubmit")
async def resubmit(
    submission_id: str,
    principal: PrincipalDep,
    request: Request,
    description: Annotated[str, Form()] = "",
    image: UploadFile = File(...),
):
    require_role(principal, "CHILD")
    env = env_for(request)
    submission = await resource_in_family(env, "submissions", submission_id, principal.family_id)
    if submission["child_user_id"] != principal.user_id:
        raise HTTPException(status_code=403, detail="This submission belongs to another profile")
    if submission["status"] != "CHANGES_REQUESTED":
        raise HTTPException(status_code=409, detail="This submission cannot be resubmitted")
    content = await validate_image(image)
    revision, image_id, now = int(submission["current_revision"]) + 1, new_id(), utc_now()
    object_key = (
        f"families/{principal.family_id}/submissions/{submission_id}/"
        f"{image_id}.{image_extension(image.content_type)}"
    )
    await env.PHOTOS.put(object_key, content)
    try:
        await batch(
            env,
            [
                env.DB.prepare(
                    """
                    INSERT INTO submission_images
                    (id, submission_id, revision, r2_object_key, content_type, file_size, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                ).bind(
                    image_id,
                    submission_id,
                    revision,
                    object_key,
                    image.content_type,
                    len(content),
                    now,
                ),
                env.DB.prepare(
                    """
                    UPDATE submissions SET status = 'PENDING', current_revision = ?,
                      description = ?, review_comment = NULL, reviewed_by_user_id = NULL,
                      reviewed_at = NULL, updated_at = ?
                    WHERE id = ? AND status = 'CHANGES_REQUESTED'
                    """
                ).bind(revision, description.strip() or submission["description"], now, submission_id),
            ],
        )
    except Exception:
        await env.PHOTOS.delete(object_key)
        raise
    return {"id": submission_id, "status": "PENDING", "current_revision": revision}


@app.post("/api/v1/submissions/{submission_id}/approve")
async def approve_submission(
    submission_id: str, payload: ReviewSubmission, principal: PrincipalDep, request: Request
):
    require_role(principal, "PARENT")
    env = env_for(request)
    submission = await resource_in_family(env, "submissions", submission_id, principal.family_id)
    if submission["status"] != "PENDING":
        raise HTTPException(status_code=409, detail="Submission is no longer pending")
    transaction_id, now = new_id(), utc_now()
    statements = [
        env.DB.prepare(
            """
            UPDATE submissions SET status = 'APPROVED', awarded_points = ?,
              reviewed_by_user_id = ?, reviewed_at = ?, updated_at = ?
            WHERE id = ? AND status = 'PENDING'
            """
        ).bind(payload.awarded_points, principal.user_id, now, now, submission_id),
        env.DB.prepare(
            """
            INSERT INTO point_transactions
            (id, family_id, user_id, transaction_type, amount, submission_id,
             reason, created_by_user_id, created_at)
            VALUES (?, ?, ?, 'SUBMISSION_REWARD', ?, ?, ?, ?, ?)
            """
        ).bind(
            transaction_id,
            principal.family_id,
            submission["child_user_id"],
            payload.awarded_points,
            submission_id,
            f"Approved: {submission['title']}",
            principal.user_id,
            now,
        ),
    ]
    if submission["chore_id"] and submission.get("chore_id"):
        chore = await row(env, "SELECT mode FROM chores WHERE id = ?", submission["chore_id"])
        if chore and chore["mode"] == "ONE_TIME":
            statements.append(
                env.DB.prepare(
                    "UPDATE chores SET state = 'COMPLETED', updated_at = ? WHERE id = ?"
                ).bind(now, submission["chore_id"])
            )
    await batch(env, statements)
    return {"id": submission_id, "status": "APPROVED", "awarded_points": payload.awarded_points}


@app.post("/api/v1/submissions/{submission_id}/reject")
async def reject_submission(
    submission_id: str, payload: RedemptionReview, principal: PrincipalDep, request: Request
):
    require_role(principal, "PARENT")
    return await finish_submission_review(
        env_for(request), principal, submission_id, "REJECTED", payload.comment
    )


@app.post("/api/v1/submissions/{submission_id}/request-changes")
async def request_submission_changes(
    submission_id: str, payload: ReviewComment, principal: PrincipalDep, request: Request
):
    require_role(principal, "PARENT")
    return await finish_submission_review(
        env_for(request), principal, submission_id, "CHANGES_REQUESTED", payload.comment
    )


async def finish_submission_review(
    env: Any, principal: Principal, submission_id: str, status: str, comment: str
) -> dict:
    submission = await resource_in_family(env, "submissions", submission_id, principal.family_id)
    if submission["status"] != "PENDING":
        raise HTTPException(status_code=409, detail="Submission is no longer pending")
    now = utc_now()
    statements = [
        env.DB.prepare(
            """
            UPDATE submissions SET status = ?, review_comment = ?, reviewed_by_user_id = ?,
              reviewed_at = ?, updated_at = ? WHERE id = ? AND status = 'PENDING'
            """
        ).bind(status, comment.strip(), principal.user_id, now, now, submission_id)
    ]
    if (
        status == "REJECTED"
        and submission["chore_id"]
        and await row(env, "SELECT mode FROM chores WHERE id = ? AND mode = 'ONE_TIME'", submission["chore_id"])
    ):
        statements.append(
            env.DB.prepare(
                "UPDATE chores SET state = 'ACTIVE', updated_at = ? WHERE id = ? AND state = 'LOCKED'"
            ).bind(now, submission["chore_id"])
        )
    await batch(env, statements)
    return {"id": submission_id, "status": status, "review_comment": comment.strip()}


async def balance_for(env: Any, user_id: str) -> int:
    result = await row(
        env, "SELECT COALESCE(SUM(amount), 0) AS balance FROM point_transactions WHERE user_id = ?", user_id
    )
    return int(result["balance"])


@app.get("/api/v1/points/balance")
async def get_balance(principal: PrincipalDep, request: Request, child_user_id: str | None = None):
    env = env_for(request)
    target = principal.user_id
    if principal.role == "PARENT":
        if not child_user_id:
            raise HTTPException(status_code=422, detail="Select a child profile")
        await child_in_family(env, principal.family_id, child_user_id)
        target = child_user_id
    return {"user_id": target, "balance": await balance_for(env, target)}


@app.get("/api/v1/points/history")
async def points_history(
    principal: PrincipalDep, request: Request, child_user_id: str | None = None
):
    env = env_for(request)
    target = principal.user_id
    if principal.role == "PARENT":
        if not child_user_id:
            raise HTTPException(status_code=422, detail="Select a child profile")
        await child_in_family(env, principal.family_id, child_user_id)
        target = child_user_id
    return await rows(
        env,
        """
        SELECT id, transaction_type, amount, reason, created_at
        FROM point_transactions WHERE user_id = ?
        ORDER BY created_at DESC LIMIT 50
        """,
        target,
    )


@app.post("/api/v1/points/adjustments", status_code=201)
async def create_adjustment(
    payload: AdjustmentCreate, principal: PrincipalDep, request: Request
):
    require_role(principal, "PARENT")
    if payload.amount == 0:
        raise HTTPException(status_code=422, detail="Adjustment cannot be zero")
    env = env_for(request)
    await child_in_family(env, principal.family_id, payload.child_user_id)
    current = await balance_for(env, payload.child_user_id)
    if current + payload.amount < 0:
        raise HTTPException(status_code=409, detail="Adjustment would make the balance negative")
    transaction_id, now = new_id(), utc_now()
    await run(
        env,
        """
        INSERT INTO point_transactions
        (id, family_id, user_id, transaction_type, amount, reason, created_by_user_id, created_at)
        VALUES (?, ?, ?, 'MANUAL_ADJUSTMENT', ?, ?, ?, ?)
        """,
        transaction_id,
        principal.family_id,
        payload.child_user_id,
        payload.amount,
        payload.reason.strip(),
        principal.user_id,
        now,
    )
    return {"id": transaction_id, **payload.model_dump(), "created_at": now}


@app.get("/api/v1/rewards")
async def list_rewards(principal: PrincipalDep, request: Request):
    if principal.role == "CHILD":
        where = "family_id = ? AND is_active = 1"
    else:
        where = "family_id = ?"
    return await rows(
        env_for(request),
        f"SELECT * FROM rewards WHERE {where} ORDER BY created_at DESC",
        principal.family_id,
    )


@app.post("/api/v1/rewards", status_code=201)
async def create_reward(payload: RewardWrite, principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    reward_id, now = new_id(), utc_now()
    await run(
        env_for(request),
        """
        INSERT INTO rewards
        (id, family_id, name, description, point_cost, created_by_user_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        reward_id,
        principal.family_id,
        payload.name.strip(),
        payload.description.strip(),
        payload.point_cost,
        principal.user_id,
        now,
        now,
    )
    return {"id": reward_id, **payload.model_dump(), "is_active": 1, "created_at": now}


@app.patch("/api/v1/rewards/{reward_id}")
async def update_reward(
    reward_id: str, payload: RewardWrite, principal: PrincipalDep, request: Request
):
    require_role(principal, "PARENT")
    env = env_for(request)
    await resource_in_family(env, "rewards", reward_id, principal.family_id)
    await run(
        env,
        """
        UPDATE rewards SET name = ?, description = ?, point_cost = ?, updated_at = ?
        WHERE id = ?
        """,
        payload.name.strip(),
        payload.description.strip(),
        payload.point_cost,
        utc_now(),
        reward_id,
    )
    return {"id": reward_id, **payload.model_dump()}


@app.delete("/api/v1/rewards/{reward_id}", status_code=204)
async def deactivate_reward(reward_id: str, principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    env = env_for(request)
    await resource_in_family(env, "rewards", reward_id, principal.family_id)
    await run(env, "UPDATE rewards SET is_active = 0, updated_at = ? WHERE id = ?", utc_now(), reward_id)
    return Response(status_code=204)


@app.post("/api/v1/rewards/{reward_id}/redemptions", status_code=201)
async def request_redemption(reward_id: str, principal: PrincipalDep, request: Request):
    require_role(principal, "CHILD")
    env = env_for(request)
    reward = await resource_in_family(env, "rewards", reward_id, principal.family_id)
    if not reward["is_active"]:
        raise HTTPException(status_code=409, detail="This reward is no longer available")
    if await balance_for(env, principal.user_id) < int(reward["point_cost"]):
        raise HTTPException(status_code=409, detail="You do not have enough points")
    redemption_id, now = new_id(), utc_now()
    try:
        await run(
            env,
            """
            INSERT INTO reward_redemptions
            (id, family_id, reward_id, child_user_id, point_cost_snapshot, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            redemption_id,
            principal.family_id,
            reward_id,
            principal.user_id,
            reward["point_cost"],
            now,
            now,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail="You already requested this reward") from exc
    return {"id": redemption_id, "status": "PENDING", "point_cost_snapshot": reward["point_cost"]}


REDEMPTION_SELECT = """
SELECT rr.*, r.name AS reward_name, u.display_name AS child_name
FROM reward_redemptions rr
JOIN rewards r ON r.id = rr.reward_id
JOIN users u ON u.id = rr.child_user_id
"""


@app.get("/api/v1/redemptions/mine")
async def my_redemptions(principal: PrincipalDep, request: Request):
    require_role(principal, "CHILD")
    return await rows(
        env_for(request),
        REDEMPTION_SELECT + " WHERE rr.child_user_id = ? ORDER BY rr.created_at DESC LIMIT 50",
        principal.user_id,
    )


@app.get("/api/v1/redemptions/pending")
async def pending_redemptions(principal: PrincipalDep, request: Request):
    require_role(principal, "PARENT")
    return await rows(
        env_for(request),
        REDEMPTION_SELECT
        + " WHERE rr.family_id = ? AND rr.status = 'PENDING' ORDER BY rr.created_at",
        principal.family_id,
    )


@app.post("/api/v1/redemptions/{redemption_id}/approve")
async def approve_redemption(
    redemption_id: str, payload: RedemptionReview, principal: PrincipalDep, request: Request
):
    require_role(principal, "PARENT")
    env = env_for(request)
    redemption = await resource_in_family(
        env, "reward_redemptions", redemption_id, principal.family_id
    )
    if redemption["status"] != "PENDING":
        raise HTTPException(status_code=409, detail="Request is no longer pending")
    balance = await balance_for(env, redemption["child_user_id"])
    cost = int(redemption["point_cost_snapshot"])
    if balance < cost:
        raise HTTPException(status_code=409, detail="The child no longer has enough points")
    now, transaction_id = utc_now(), new_id()
    await batch(
        env,
        [
            env.DB.prepare(
                """
                INSERT INTO point_transactions
                (id, family_id, user_id, transaction_type, amount, redemption_id,
                 reason, created_by_user_id, created_at)
                SELECT ?, ?, rr.child_user_id, 'REWARD_REDEMPTION', -rr.point_cost_snapshot,
                  rr.id, 'Reward redeemed', ?, ?
                FROM reward_redemptions rr
                WHERE rr.id = ? AND rr.status = 'PENDING'
                  AND (SELECT COALESCE(SUM(amount), 0) FROM point_transactions
                       WHERE user_id = rr.child_user_id) >= rr.point_cost_snapshot
                """
            ).bind(
                transaction_id,
                principal.family_id,
                principal.user_id,
                now,
                redemption_id,
            ),
            env.DB.prepare(
                """
                UPDATE reward_redemptions SET status = 'APPROVED', review_comment = ?,
                  reviewed_by_user_id = ?, reviewed_at = ?, updated_at = ?
                WHERE id = ? AND status = 'PENDING'
                  AND EXISTS (
                    SELECT 1 FROM point_transactions
                    WHERE redemption_id = ? AND transaction_type = 'REWARD_REDEMPTION'
                  )
                """
            ).bind(
                payload.comment.strip(),
                principal.user_id,
                now,
                now,
                redemption_id,
                redemption_id,
            ),
        ],
    )
    approved = await row(env, "SELECT status FROM reward_redemptions WHERE id = ?", redemption_id)
    if approved["status"] != "APPROVED":
        raise HTTPException(status_code=409, detail="Request could not be approved")
    return {"id": redemption_id, "status": "APPROVED", "points_deducted": cost}


@app.post("/api/v1/redemptions/{redemption_id}/reject")
async def reject_redemption(
    redemption_id: str, payload: RedemptionReview, principal: PrincipalDep, request: Request
):
    require_role(principal, "PARENT")
    env = env_for(request)
    redemption = await resource_in_family(
        env, "reward_redemptions", redemption_id, principal.family_id
    )
    if redemption["status"] != "PENDING":
        raise HTTPException(status_code=409, detail="Request is no longer pending")
    now = utc_now()
    await run(
        env,
        """
        UPDATE reward_redemptions SET status = 'REJECTED', review_comment = ?,
          reviewed_by_user_id = ?, reviewed_at = ?, updated_at = ?
        WHERE id = ? AND status = 'PENDING'
        """,
        payload.comment.strip(),
        principal.user_id,
        now,
        now,
        redemption_id,
    )
    return {"id": redemption_id, "status": "REJECTED"}
