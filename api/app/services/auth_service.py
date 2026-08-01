from __future__ import annotations

import base64
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from app.db import Database, to_python
from app.errors import (
    AuthenticationFailed,
    Conflict,
    InvalidRequest,
    PermissionDenied,
    ServiceUnavailable,
)
from app.models import (
    AccountLogin,
    AccountRegister,
    GoogleAuth,
    HouseholdCreate,
)
from app.repositories.auth import AuthRepository
from app.repositories.families import FamilyRepository
from app.scheduling import timezone_is_valid
from app.security import (
    Principal,
    create_access_token,
    decode_access_token,
    hash_credential,
    hash_token,
    new_family_code,
    verify_credential,
)
from app.services.common import env_value, new_id, utc_now


class LoginRateLimited(AuthenticationFailed):
    status_code = 429


class HouseholdLocked(PermissionDenied):
    status_code = 423


class AuthService:
    def __init__(
        self,
        db: Database,
        env: Any,
        auth: AuthRepository,
        families: FamilyRepository,
    ):
        self.db = db
        self.env = env
        self.auth = auth
        self.families = families

    async def resolve_principal(
        self, token: str, path: str
    ) -> Principal:
        try:
            claims = decode_access_token(
                token, env_value(self.env, "JWT_SECRET")
            )
        except ValueError as exc:
            raise AuthenticationFailed(
                "Session expired or invalid"
            ) from exc
        account = await self.auth.account_by_id(str(claims.get("sub", "")))
        if not account:
            raise AuthenticationFailed("Account is unavailable")
        claimed_family = claims.get("family_id")
        if claimed_family and claimed_family != account.get("family_id"):
            raise AuthenticationFailed("Household membership changed. Sign in again.")
        deletion_scheduled_for = account.pop(
            "deletion_scheduled_for", None
        )
        allowed = {
            "/api/v1/auth/me",
            "/api/v1/auth/logout",
            "/api/v1/account/deletion/cancel",
            "/api/v1/push/devices",
        }
        if (
            deletion_scheduled_for
            and account["role"] == "PARENT"
            and path not in allowed
        ):
            raise HouseholdLocked(
                "Household deletion is pending. Cancel it in Settings to restore access."
            )
        return Principal(
            user_id=account["user_id"],
            email=account["email"],
            display_name=account["display_name"],
            family_id=account.get("family_id"),
            role=account.get("role"),
        )

    @staticmethod
    def require_role(principal: Principal, role: str) -> None:
        if principal.role != role:
            raise PermissionDenied(f"{role.title()} access required")

    async def issue_session(self, account: dict) -> dict:
        now = datetime.now(UTC)
        refresh = secrets.token_urlsafe(48)
        await self.auth.create_session(
            new_id(),
            account["user_id"],
            hash_token(refresh),
            (now + timedelta(days=30)).isoformat(),
            now.isoformat(),
        )
        claims = {
            "sub": account["user_id"],
        }
        if account.get("family_id"):
            claims["family_id"] = account["family_id"]
            claims["role"] = account["role"]
        public_account = {
            key: value
            for key, value in account.items()
            if key not in {"credential_hash", "credential_salt", "session_id"}
        }
        return {
            "access_token": create_access_token(
                claims, env_value(self.env, "JWT_SECRET")
            ),
            "refresh_token": refresh,
            "expires_in": 900,
            "user": public_account,
        }

    async def issue_session_for_user(self, user_id: str) -> dict:
        account = await self.auth.account_by_id(user_id)
        if not account:
            raise AuthenticationFailed("Account is unavailable")
        return await self.issue_session(account)

    def identity_hash(self, value: str) -> str:
        return hash_token(
            f"{value.casefold()}:{env_value(self.env, 'CREDENTIAL_PEPPER')}"
        )

    async def check_login_lock(self, identity: str) -> None:
        attempt = await self.auth.login_attempt(identity)
        if (
            attempt
            and attempt["locked_until"]
            and attempt["locked_until"] > utc_now()
        ):
            raise LoginRateLimited(
                "Too many attempts. Try again in 15 minutes."
            )

    async def failed_login(self, identity: str) -> None:
        now = datetime.now(UTC)
        current = await self.auth.login_attempt(identity)
        attempts = int(current["attempts"]) + 1 if current else 1
        locked_until = (
            (now + timedelta(minutes=15)).isoformat()
            if attempts >= 5
            else None
        )
        await self.auth.record_login_attempt(
            identity, attempts, locked_until, now.isoformat()
        )

    async def register_account(self, payload: AccountRegister) -> dict:
        email = payload.email.strip().casefold()
        if await self.auth.email_exists(email):
            raise Conflict("An account already uses this email")
        user_id, now = new_id(), utc_now()
        password_hash, salt = hash_credential(
            payload.password, env_value(self.env, "CREDENTIAL_PEPPER")
        )
        await self.db.batch([
            self.auth.create_account_statement(
                user_id, email, payload.display_name.strip(),
                password_hash, salt, True, now
            )
        ])
        return await self.issue_session(
            await self.auth.account_by_id(user_id)
        )

    async def login_account(self, payload: AccountLogin) -> dict:
        email = payload.email.strip().casefold()
        identity = self.identity_hash(f"account:{email}")
        await self.check_login_lock(identity)
        account = await self.auth.account_by_email(email)
        valid = account and verify_credential(
            payload.password,
            env_value(self.env, "CREDENTIAL_PEPPER"),
            account["credential_salt"],
            account["credential_hash"],
        )
        if not valid:
            await self.failed_login(identity)
            raise AuthenticationFailed("Incorrect email or password")
        await self.auth.clear_login_attempts(identity)
        return await self.issue_session(account)

    async def create_household(
        self, principal: Principal, payload: HouseholdCreate
    ) -> dict:
        if principal.family_id:
            raise Conflict("This account already belongs to a household")
        if not timezone_is_valid(payload.timezone):
            raise InvalidRequest("Device timezone is invalid")
        family_id, member_id, code, now = (
            new_id(), new_id(), new_family_code(), utc_now()
        )
        await self.db.batch([
            self.families.create_statement(
                family_id, payload.family_name.strip(), code,
                payload.timezone, now
            ),
            self.auth.create_parent_member_statement(
                member_id, family_id, principal.user_id, now
            ),
        ])
        return await self.issue_session(
            await self.auth.account_by_id(principal.user_id)
        )

    async def refresh(self, refresh_token: str) -> dict:
        now = utc_now()
        session = await self.auth.refresh_account(
            hash_token(refresh_token), now
        )
        if not session:
            raise AuthenticationFailed(
                "Refresh session expired or invalid"
            )
        await self.auth.revoke_session(session["session_id"], now)
        return await self.issue_session(session)

    async def logout(self, refresh_token: str) -> None:
        await self.auth.revoke_by_token(
            hash_token(refresh_token), utc_now()
        )

    async def me(self, principal: Principal) -> dict:
        if not principal.family_id:
            return principal.__dict__
        family = await self.families.find_by_id(principal.family_id)
        if not family:
            raise AuthenticationFailed("Household is unavailable")
        return {
            **principal.__dict__,
            "family_name": family["name"],
            "family_code": family["access_code"],
            "timezone": family["timezone"],
            "deletion_scheduled_for": family["deletion_scheduled_for"],
        }

    def realtime_ticket(self, principal: Principal) -> dict:
        if not principal.family_id or not principal.role:
            raise PermissionDenied("Join or create a household first")
        return {
            "ticket": create_access_token(
                {
                    "sub": principal.user_id,
                    "family_id": principal.family_id,
                    "role": principal.role,
                    "purpose": "realtime",
                },
                env_value(self.env, "JWT_SECRET"),
                ttl_seconds=30,
            ),
            "expires_in": 30,
        }

    async def create_google_nonce(self) -> dict:
        nonce = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        await self.auth.create_nonce(
            new_id(),
            hash_token(nonce),
            (now + timedelta(minutes=10)).isoformat(),
            now.isoformat(),
        )
        await self.auth.delete_old_nonces(
            (now - timedelta(days=1)).isoformat()
        )
        return {"nonce": nonce, "expires_in": 600}

    @staticmethod
    def _decode_google_claims(token: str) -> dict:
        try:
            encoded = token.split(".")[1]
            encoded += "=" * (-len(encoded) % 4)
            return json.loads(base64.urlsafe_b64decode(encoded))
        except Exception as exc:
            raise AuthenticationFailed(
                "Google sign-in token is invalid"
            ) from exc

    async def verify_google_identity(
        self, id_token: str, nonce: str
    ) -> dict:
        from workers import fetch as worker_fetch

        nonce_record = await self.auth.find_nonce(
            hash_token(nonce), utc_now()
        )
        if not nonce_record:
            raise AuthenticationFailed(
                "Google sign-in attempt expired. Please try again."
            )
        response = await worker_fetch(
            "https://oauth2.googleapis.com/tokeninfo?"
            + urlencode({"id_token": id_token})
        )
        if response.status != 200:
            raise AuthenticationFailed(
                "Google could not verify this sign-in"
            )
        verified = to_python(await response.json())
        claims = self._decode_google_claims(id_token)
        audiences = {
            value
            for value in (
                env_value(self.env, "GOOGLE_ANDROID_CLIENT_ID"),
                env_value(self.env, "GOOGLE_WEB_CLIENT_ID"),
            )
            if value
        }
        if not audiences:
            raise ServiceUnavailable("Google sign-in is not configured")
        if verified.get("aud") not in audiences:
            raise AuthenticationFailed(
                "Google sign-in was issued for a different app"
            )
        if verified.get("email_verified") not in (True, "true"):
            raise AuthenticationFailed(
                "Use a verified Google email address"
            )
        if claims.get("nonce") != nonce:
            raise AuthenticationFailed(
                "Google sign-in security check failed"
            )
        if await self.auth.use_nonce(nonce_record["id"], utc_now()) != 1:
            raise AuthenticationFailed(
                "Google sign-in attempt expired. Please try again."
            )
        return {
            "subject": str(verified["sub"]),
            "email": str(verified["email"]).strip().casefold(),
            "name": str(
                verified.get("name") or verified.get("given_name") or ""
            ).strip(),
        }

    async def login_google(self, payload: GoogleAuth) -> dict:
        identity = await self.verify_google_identity(
            payload.id_token, payload.nonce
        )
        account = await self.auth.google_account(identity["subject"])
        if account:
            return await self.issue_session(account)
        existing = await self.auth.account_by_email(
            identity["email"], password_required=False
        )
        if existing:
            try:
                await self.auth.create_identity(
                    new_id(),
                    existing["user_id"],
                    identity["subject"],
                    identity["email"],
                    utc_now(),
                )
            except Exception as exc:
                raise Conflict(
                    "This Google identity is already linked to another account"
                ) from exc
            return await self.issue_session(existing)
        user_id, now = new_id(), utc_now()
        credential_hash, salt = hash_credential(
            secrets.token_urlsafe(48),
            env_value(self.env, "CREDENTIAL_PEPPER"),
        )
        statements = [
            self.auth.create_account_statement(
                user_id,
                identity["email"],
                identity["name"] or "Google user",
                credential_hash,
                salt,
                False,
                now,
            ),
            self.auth.create_identity_statement(
                new_id(), user_id, identity["subject"], identity["email"], now
            ),
        ]
        await self.db.batch(statements)
        return await self.issue_session(await self.auth.account_by_id(user_id))

    async def confirm_parent(
        self,
        principal: Principal,
        password: str | None,
        google_id_token: str | None,
        nonce: str | None,
    ) -> None:
        account = await self.auth.parent_auth(principal.user_id)
        if (
            password
            and account
            and int(account["password_login_enabled"]) == 1
            and verify_credential(
                password,
                env_value(self.env, "CREDENTIAL_PEPPER"),
                account["credential_salt"],
                account["credential_hash"],
            )
        ):
            return
        if google_id_token and nonce:
            identity = await self.verify_google_identity(
                google_id_token, nonce
            )
            if await self.auth.linked_identity(
                principal.user_id, identity["subject"]
            ):
                return
        raise AuthenticationFailed(
            "Confirm your parent sign-in to continue"
        )
