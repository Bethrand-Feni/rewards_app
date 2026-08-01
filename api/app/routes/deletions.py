from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import PrincipalDep, ServicesDep
from app.models import FamilyDeletionCreate


router = APIRouter()


@router.post("/api/v1/account/deletion")
async def schedule_family_deletion(
    payload: FamilyDeletionCreate,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.deletions.schedule_family(principal, payload)


@router.post("/api/v1/account/deletion/cancel")
async def cancel_family_deletion(
    principal: PrincipalDep, services: ServicesDep
):
    services.auth.require_role(principal, "PARENT")
    return await services.deletions.cancel_family(principal)


@router.post("/api/v1/household/children/{child_id}/deletion")
async def schedule_child_deletion(
    child_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.deletions.schedule_child(
        principal, child_id
    )


@router.post(
    "/api/v1/household/children/{child_id}/deletion/cancel"
)
async def cancel_child_deletion(
    child_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.deletions.cancel_child(principal, child_id)
