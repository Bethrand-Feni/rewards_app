from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import PrincipalDep, ServicesDep
from app.models import AdjustmentCreate


router = APIRouter()


@router.get("/api/v1/points/balance")
async def get_balance(
    principal: PrincipalDep,
    services: ServicesDep,
    child_user_id: str | None = None,
):
    return await services.points.balance(
        principal.family_id,
        principal.user_id,
        principal.role,
        child_user_id,
    )


@router.get("/api/v1/points/history")
async def points_history(
    principal: PrincipalDep,
    services: ServicesDep,
    child_user_id: str | None = None,
):
    return await services.points.history(
        principal.family_id,
        principal.user_id,
        principal.role,
        child_user_id,
    )


@router.post("/api/v1/points/adjustments", status_code=201)
async def create_adjustment(
    payload: AdjustmentCreate,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.points.adjust(
        principal.family_id, principal.user_id, payload
    )
