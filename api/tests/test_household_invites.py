from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models import HouseholdInviteCreate
from app.repositories.household_invites import HouseholdInviteRepository
from app.services.household_service import HouseholdService


class FakeFamilies:
    async def find_by_id(self, family_id: str):
        return {
            "id": family_id,
            "name": "Feni Family",
            "access_code": "FENI42",
        }


class FakeInvites:
    def __init__(self):
        self.created = None

    async def create(self, *values):
        self.created = values


class Env:
    CREDENTIAL_PEPPER = "test-pepper"


@pytest.mark.asyncio
async def test_invite_uses_requested_role_and_expires_in_one_hour() -> None:
    invites = FakeInvites()
    service = HouseholdService(
        object(), Env(), FakeFamilies(), object(), invites, object()
    )

    result = await service.create_invite(
        "family-1",
        "parent-1",
        HouseholdInviteCreate(role="CHILD"),
    )

    created_at = datetime.fromisoformat(invites.created[6])
    expires_at = datetime.fromisoformat(invites.created[4])
    assert (expires_at - created_at).total_seconds() == 3600
    assert result["role"] == "CHILD"
    assert result["family_code"] == "FENI42"
    assert len(result["join_pin"]) == 6


def test_invite_role_cannot_be_self_selected_outside_allowed_roles() -> None:
    with pytest.raises(ValidationError):
        HouseholdInviteCreate(role="ADMIN")


def test_redeeming_invite_creates_membership_then_consumes_code() -> None:
    repository = HouseholdInviteRepository(object())
    statements = repository.redeem_statements(
        "member-1", "account-1", "invite-1", "2026-08-01T10:00:00+00:00"
    )

    assert len(statements) == 2
    assert "SELECT" in statements[0].sql
    assert statements[0].params[1] == "account-1"
    assert "consumed_at" in statements[1].sql
