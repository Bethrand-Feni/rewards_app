from __future__ import annotations

from fastapi import APIRouter, Response

from app.dependencies import PrincipalDep, ServicesDep
from app.models import ChoreWrite


router = APIRouter()


@router.get("/api/v1/chores")
async def list_chores(
    principal: PrincipalDep, services: ServicesDep
):
    return await services.chores.list(
        principal.family_id, principal.user_id, principal.role
    )


@router.post("/api/v1/chores", status_code=201)
async def create_chore(
    payload: ChoreWrite,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.chores.create(
        principal.family_id, principal.user_id, payload
    )


@router.patch("/api/v1/chores/{chore_id}")
async def update_chore(
    chore_id: str,
    payload: ChoreWrite,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.chores.update(
        principal.family_id, chore_id, payload
    )


@router.delete("/api/v1/chores/{chore_id}", status_code=204)
async def deactivate_chore(
    chore_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    await services.chores.deactivate(principal.family_id, chore_id)
    return Response(status_code=204)
