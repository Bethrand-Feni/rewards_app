from __future__ import annotations

from fastapi import APIRouter, Response

from app.dependencies import PrincipalDep, ServicesDep
from app.models import (
    ChildCreate,
    ChildUpdate,
    HouseholdCreate,
    HouseholdInviteCreate,
    HouseholdJoin,
)


router = APIRouter()


@router.post("/api/v1/households", status_code=201)
async def create_household(
    payload: HouseholdCreate,
    principal: PrincipalDep,
    services: ServicesDep,
):
    return await services.auth.create_household(principal, payload)


@router.post("/api/v1/households/join")
async def join_household(
    payload: HouseholdJoin,
    principal: PrincipalDep,
    services: ServicesDep,
):
    return await services.household.join_household(principal, payload)


@router.get("/api/v1/household/members")
async def list_members(
    principal: PrincipalDep, services: ServicesDep
):
    services.auth.require_role(principal, "PARENT")
    return await services.household.list_members(principal.family_id)


@router.post("/api/v1/household/invites", status_code=201)
async def create_household_invite(
    payload: HouseholdInviteCreate,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.household.create_invite(
        principal.family_id, principal.user_id, payload
    )


@router.get("/api/v1/household/children")
async def list_children(
    principal: PrincipalDep, services: ServicesDep
):
    services.auth.require_role(principal, "PARENT")
    return await services.household.list_children(principal.family_id)


@router.post("/api/v1/household/children", status_code=201)
async def create_child(
    payload: ChildCreate,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.household.create_child(
        principal.family_id, payload
    )


@router.patch("/api/v1/household/children/{child_id}")
async def update_child(
    child_id: str,
    payload: ChildUpdate,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.household.update_child(
        principal.family_id, child_id, payload
    )


@router.post("/api/v1/household/children/{child_id}/join-pin")
async def regenerate_child_join_pin(
    child_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.household.regenerate_join_pin(
        principal.family_id, child_id
    )


@router.patch(
    "/api/v1/household/children/{child_id}/deactivate",
    status_code=204,
)
async def deactivate_child(
    child_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    await services.household.deactivate_child(
        principal.family_id, child_id
    )
    return Response(status_code=204)


@router.post("/api/v1/household/rotate-code")
async def rotate_family_code(
    principal: PrincipalDep, services: ServicesDep
):
    services.auth.require_role(principal, "PARENT")
    return await services.household.rotate_code(principal.family_id)
