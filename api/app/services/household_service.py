from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from app.db import Database
from app.errors import (
    AuthenticationFailed,
    Conflict,
    ResourceNotFound,
    ServiceUnavailable,
)
from app.models import (
    ChildCreate,
    ChildUpdate,
    HouseholdInviteCreate,
    HouseholdJoin,
)
from app.repositories.children import ChildRepository
from app.repositories.families import FamilyRepository
from app.repositories.household_invites import HouseholdInviteRepository
from app.realtime_contract import publish_realtime
from app.security import (
    Principal,
    hash_credential,
    hash_token,
    new_family_code,
    new_join_pin,
)
from app.services.common import env_value, new_id, utc_now

if TYPE_CHECKING:
    from app.services.auth_service import AuthService


class HouseholdService:
    def __init__(
        self,
        db: Database,
        env: Any,
        families: FamilyRepository,
        children: ChildRepository,
        invites: HouseholdInviteRepository,
        auth: AuthService,
    ):
        self.db = db
        self.env = env
        self.families = families
        self.children = children
        self.invites = invites
        self.auth = auth

    async def list_members(self, family_id: str) -> list[dict]:
        return await self.invites.list_members(family_id)

    async def create_invite(
        self,
        family_id: str,
        created_by_user_id: str,
        payload: HouseholdInviteCreate,
    ) -> dict:
        family = await self.families.find_by_id(family_id)
        if not family:
            raise ResourceNotFound("Household not found")
        now = datetime.now(UTC)
        expires_at = (now + timedelta(hours=1)).isoformat()
        for _ in range(8):
            pin = new_join_pin()
            pin_hash = hash_token(
                f"{family_id}:{pin}:"
                f"{env_value(self.env, 'CREDENTIAL_PEPPER')}"
            )
            try:
                await self.invites.create(
                    new_id(),
                    family_id,
                    payload.role,
                    pin_hash,
                    expires_at,
                    created_by_user_id,
                    now.isoformat(),
                )
                return {
                    "family_name": family["name"],
                    "family_code": family["access_code"],
                    "join_pin": pin,
                    "role": payload.role,
                    "expires_at": expires_at,
                }
            except Exception:
                continue
        raise ServiceUnavailable("Could not generate a unique join PIN")

    async def list_children(self, family_id: str) -> list[dict]:
        return await self.children.list_for_family(family_id)

    async def require_child(self, family_id: str, child_id: str) -> dict:
        child = await self.children.find_in_family(child_id, family_id)
        if not child:
            raise ResourceNotFound("Child profile not found")
        return child

    async def create_child(
        self, family_id: str, payload: ChildCreate
    ) -> dict:
        child_id, member_id, now = new_id(), new_id(), utc_now()
        credential_hash, salt = hash_credential(
            secrets.token_urlsafe(32),
            env_value(self.env, "CREDENTIAL_PEPPER"),
        )
        await self.db.batch(
            self.children.create_statements(
                child_id,
                member_id,
                family_id,
                payload.display_name.strip(),
                credential_hash,
                salt,
                now,
            )
        )
        invite = await self._create_join_invite(family_id, child_id)
        await publish_realtime(
            self.env, family_id, "children.changed", "parents"
        )
        return {
            "id": child_id,
            "display_name": payload.display_name.strip(),
            "claim_status": "WAITING",
            **invite,
        }

    async def update_child(
        self, family_id: str, child_id: str, payload: ChildUpdate
    ) -> dict:
        await self.require_child(family_id, child_id)
        await self.db.batch(
            self.children.update_statements(
                child_id,
                family_id,
                payload.display_name.strip(),
                utc_now(),
            )
        )
        await publish_realtime(
            self.env, family_id, "children.changed", "household"
        )
        return {
            "id": child_id,
            "display_name": payload.display_name.strip(),
        }

    async def _create_join_invite(
        self, family_id: str, child_id: str
    ) -> dict:
        family = await self.families.find_by_id(family_id)
        if not family:
            raise ResourceNotFound("Household not found")
        pin = new_join_pin()
        now = datetime.now(UTC)
        expires_at = (now + timedelta(hours=1)).isoformat()
        pin_hash = hash_token(
            f"{family_id}:{pin}:"
            f"{env_value(self.env, 'CREDENTIAL_PEPPER')}"
        )
        await self.children.upsert_join_invite(
            new_id(), family_id, child_id, pin_hash,
            expires_at, now.isoformat()
        )
        return {"join_pin": pin, "join_pin_expires_at": expires_at}

    async def regenerate_join_pin(
        self, family_id: str, child_id: str
    ) -> dict:
        child = await self.require_child(family_id, child_id)
        if child["account_type"] != "CHILD_PROFILE":
            raise Conflict("This child profile has already been claimed")
        return await self._create_join_invite(family_id, child_id)

    async def join_household(
        self, principal: Principal, payload: HouseholdJoin
    ) -> dict:
        if principal.family_id or await self.children.membership_for_user(
            principal.user_id
        ):
            raise Conflict("This account already belongs to a household")
        code = payload.family_code.strip().upper()
        identity = self.auth.identity_hash(f"join:{principal.user_id}:{code}")
        await self.auth.check_login_lock(identity)
        family = await self.families.find_by_code(code)
        pin_hash = hash_token(
            f"{family['id'] if family else 'unknown'}:{payload.join_pin}:"
            f"{env_value(self.env, 'CREDENTIAL_PEPPER')}"
        )
        now = utc_now()
        invite = await self.invites.find(
            family["id"], pin_hash, now
        ) if family else None
        legacy_invite = None
        if not invite and family:
            legacy_invite = await self.children.find_join_invite(
                family["id"], pin_hash, now
            )
            invite = legacy_invite
        if not invite:
            await self.auth.failed_login(identity)
            raise AuthenticationFailed(
                "Household code or join PIN is incorrect or expired"
            )
        if legacy_invite:
            await self.db.batch(
                self.children.claim_statements(
                    principal.user_id, legacy_invite, now
                )
            )
        else:
            results = await self.db.batch(
                self.invites.redeem_statements(
                    new_id(), principal.user_id, invite["id"], now
                )
            )
            if len(results) != 2 or any(result.changes != 1 for result in results):
                raise Conflict("This invitation has already been used")
        await self.auth.auth.clear_login_attempts(identity)
        await publish_realtime(
            self.env, invite["family_id"], "children.changed", "household"
        )
        return await self.auth.issue_session_for_user(principal.user_id)

    async def deactivate_child(self, family_id: str, child_id: str) -> None:
        await self.require_child(family_id, child_id)
        await self.db.batch(
            self.children.deactivate_statements(child_id, utc_now())
        )
        await publish_realtime(
            self.env, family_id, "children.changed", "parents"
        )

    async def rotate_code(self, family_id: str) -> dict:
        for _ in range(8):
            code = new_family_code()
            try:
                await self.families.update_access_code(family_id, code)
                return {"family_code": code}
            except Exception:
                continue
        raise ServiceUnavailable("Could not generate a household code")
