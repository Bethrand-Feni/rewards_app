from __future__ import annotations

from app.db import Database, DbStatement


ACCOUNT_BY_ID = """
SELECT
  u.id AS user_id, u.email, u.display_name, fm.family_id, fm.role,
  f.name AS family_name, f.access_code AS family_code,
  f.deletion_scheduled_for
FROM users AS u
LEFT JOIN family_members AS fm ON fm.user_id = u.id
LEFT JOIN families AS f ON f.id = fm.family_id
WHERE u.id = ?1
  AND u.is_active = 1
  AND u.account_type = 'ACCOUNT'
  AND (fm.role = 'PARENT' OR f.deletion_scheduled_for IS NULL)
LIMIT 1
"""

ACCOUNT_SELECT = """
SELECT
  u.id AS user_id, u.email, u.display_name,
  u.credential_hash, u.credential_salt, u.password_login_enabled,
  fm.family_id, fm.role, f.name AS family_name, f.access_code AS family_code
FROM users AS u
LEFT JOIN family_members AS fm ON fm.user_id = u.id
LEFT JOIN families AS f ON f.id = fm.family_id
"""

ACCOUNT_BY_EMAIL = ACCOUNT_SELECT + """
WHERE u.email = ?1
  AND u.is_active = 1
  AND u.account_type = 'ACCOUNT'
  AND u.password_login_enabled = 1
LIMIT 1
"""

ACTIVE_ACCOUNT_BY_EMAIL = ACCOUNT_SELECT + """
WHERE u.email = ?1
  AND u.is_active = 1
  AND u.account_type = 'ACCOUNT'
LIMIT 1
"""

GOOGLE_ACCOUNT = ACCOUNT_SELECT + """
JOIN auth_identities AS ai ON ai.user_id = u.id
WHERE ai.provider = 'GOOGLE'
  AND ai.provider_subject = ?1
  AND u.is_active = 1
  AND u.account_type = 'ACCOUNT'
LIMIT 1
"""

EMAIL_EXISTS = """
SELECT id FROM users WHERE email = ?1 LIMIT 1
"""

CREATE_SESSION = """
INSERT INTO auth_sessions (
  id, user_id, refresh_token_hash, expires_at, created_at
) VALUES (?1, ?2, ?3, ?4, ?5)
"""

REFRESH_ACCOUNT = """
SELECT
  s.id AS session_id, u.id AS user_id, u.email, u.display_name,
  fm.family_id, fm.role, f.name AS family_name, f.access_code AS family_code
FROM auth_sessions AS s
JOIN users AS u ON u.id = s.user_id
LEFT JOIN family_members AS fm ON fm.user_id = u.id
LEFT JOIN families AS f ON f.id = fm.family_id
WHERE s.refresh_token_hash = ?1
  AND s.revoked_at IS NULL
  AND s.expires_at > ?2
  AND u.is_active = 1
  AND u.account_type = 'ACCOUNT'
  AND (fm.role = 'PARENT' OR f.deletion_scheduled_for IS NULL)
LIMIT 1
"""

REVOKE_SESSION = """
UPDATE auth_sessions SET revoked_at = ?1 WHERE id = ?2 AND revoked_at IS NULL
"""

REVOKE_BY_TOKEN = """
UPDATE auth_sessions
SET revoked_at = ?1
WHERE refresh_token_hash = ?2
  AND revoked_at IS NULL
"""

LOGIN_ATTEMPT = """
SELECT attempts, locked_until
FROM login_attempts
WHERE identity_hash = ?1
LIMIT 1
"""

UPSERT_ATTEMPT = """
INSERT INTO login_attempts (
  identity_hash, attempts, locked_until, updated_at
) VALUES (?1, ?2, ?3, ?4)
ON CONFLICT(identity_hash) DO UPDATE SET
  attempts = excluded.attempts,
  locked_until = excluded.locked_until,
  updated_at = excluded.updated_at
"""

CLEAR_ATTEMPTS = """
DELETE FROM login_attempts WHERE identity_hash = ?1
"""

CREATE_NONCE = """
INSERT INTO oauth_nonces (id, nonce_hash, expires_at, created_at)
VALUES (?1, ?2, ?3, ?4)
"""

FIND_NONCE = """
SELECT id
FROM oauth_nonces
WHERE nonce_hash = ?1
  AND used_at IS NULL
  AND expires_at > ?2
LIMIT 1
"""

USE_NONCE = """
UPDATE oauth_nonces
SET used_at = ?1
WHERE id = ?2
  AND used_at IS NULL
"""

DELETE_OLD_NONCES = """
DELETE FROM oauth_nonces
WHERE expires_at < ?1
   OR used_at IS NOT NULL
"""

CREATE_IDENTITY = """
INSERT INTO auth_identities (
  id, user_id, provider, provider_subject, verified_email, created_at, updated_at
) VALUES (?1, ?2, 'GOOGLE', ?3, ?4, ?5, ?5)
"""

FIND_LINKED_IDENTITY = """
SELECT id
FROM auth_identities
WHERE user_id = ?1
  AND provider = 'GOOGLE'
  AND provider_subject = ?2
LIMIT 1
"""

CREATE_ACCOUNT_USER = """
INSERT INTO users (
  id, email, display_name, credential_hash, credential_salt,
  password_login_enabled, account_type, created_at, updated_at
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'ACCOUNT', ?7, ?7)
"""

CREATE_PARENT_MEMBER = """
INSERT INTO family_members (
  id, family_id, user_id, role, joined_at, claimed_at
) VALUES (?1, ?2, ?3, 'PARENT', ?4, ?4)
"""

PARENT_AUTH = """
SELECT credential_hash, credential_salt, password_login_enabled
FROM users
WHERE id = ?1
LIMIT 1
"""


class AuthRepository:
    def __init__(self, db: Database):
        self.db = db

    async def account_by_id(self, user_id: str) -> dict | None:
        return await self.db.one(ACCOUNT_BY_ID, user_id)

    async def account_by_email(
        self, email: str, password_required: bool = True
    ) -> dict | None:
        return await self.db.one(
            ACCOUNT_BY_EMAIL if password_required else ACTIVE_ACCOUNT_BY_EMAIL,
            email,
        )

    async def google_account(self, subject: str) -> dict | None:
        return await self.db.one(GOOGLE_ACCOUNT, subject)

    async def email_exists(self, email: str) -> bool:
        return await self.db.one(EMAIL_EXISTS, email) is not None

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        refresh_hash: str,
        expires_at: str,
        now: str,
    ) -> None:
        await self.db.execute(
            CREATE_SESSION,
            session_id,
            user_id,
            refresh_hash,
            expires_at,
            now,
        )

    async def refresh_account(
        self, refresh_hash: str, now: str
    ) -> dict | None:
        return await self.db.one(REFRESH_ACCOUNT, refresh_hash, now)

    async def revoke_session(self, session_id: str, now: str) -> None:
        await self.db.execute(REVOKE_SESSION, now, session_id)

    async def revoke_by_token(self, refresh_hash: str, now: str) -> None:
        await self.db.execute(REVOKE_BY_TOKEN, now, refresh_hash)

    async def login_attempt(self, identity_hash: str) -> dict | None:
        return await self.db.one(LOGIN_ATTEMPT, identity_hash)

    async def record_login_attempt(
        self,
        identity_hash: str,
        attempts: int,
        locked_until: str | None,
        now: str,
    ) -> None:
        await self.db.execute(
            UPSERT_ATTEMPT,
            identity_hash,
            attempts,
            locked_until,
            now,
        )

    async def clear_login_attempts(self, identity_hash: str) -> None:
        await self.db.execute(CLEAR_ATTEMPTS, identity_hash)

    async def create_nonce(
        self,
        nonce_id: str,
        nonce_hash: str,
        expires_at: str,
        now: str,
    ) -> None:
        await self.db.execute(
            CREATE_NONCE, nonce_id, nonce_hash, expires_at, now
        )

    async def find_nonce(
        self, nonce_hash: str, now: str
    ) -> dict | None:
        return await self.db.one(FIND_NONCE, nonce_hash, now)

    async def use_nonce(self, nonce_id: str, now: str) -> int:
        result = await self.db.execute(USE_NONCE, now, nonce_id)
        return result.changes

    async def delete_old_nonces(self, before: str) -> None:
        await self.db.execute(DELETE_OLD_NONCES, before)

    async def create_identity(
        self,
        identity_id: str,
        user_id: str,
        subject: str,
        email: str,
        now: str,
    ) -> None:
        await self.db.execute(
            CREATE_IDENTITY,
            identity_id,
            user_id,
            subject,
            email,
            now,
        )

    def create_identity_statement(
        self,
        identity_id: str,
        user_id: str,
        subject: str,
        email: str,
        now: str,
    ) -> DbStatement:
        return DbStatement(
            CREATE_IDENTITY,
            (identity_id, user_id, subject, email, now),
        )

    async def linked_identity(
        self, user_id: str, subject: str
    ) -> dict | None:
        return await self.db.one(FIND_LINKED_IDENTITY, user_id, subject)

    def create_account_statement(
        self,
        user_id: str,
        email: str,
        display_name: str,
        credential_hash: str,
        credential_salt: str,
        password_login_enabled: bool,
        now: str,
    ) -> DbStatement:
        return DbStatement(
            CREATE_ACCOUNT_USER,
            (
                user_id,
                email,
                display_name,
                credential_hash,
                credential_salt,
                int(password_login_enabled),
                now,
            ),
        )

    def create_parent_member_statement(
        self, member_id: str, family_id: str, user_id: str, now: str
    ) -> DbStatement:
        return DbStatement(
            CREATE_PARENT_MEMBER, (member_id, family_id, user_id, now)
        )

    async def parent_auth(self, user_id: str) -> dict | None:
        return await self.db.one(PARENT_AUTH, user_id)
