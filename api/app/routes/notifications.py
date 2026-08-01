from __future__ import annotations

from fastapi import APIRouter, Response

from app.dependencies import PrincipalDep, ServicesDep
from app.models import PushDeviceDelete, PushDeviceWrite


router = APIRouter()


@router.put("/api/v1/push/devices")
async def register_push_device(
    payload: PushDeviceWrite,
    principal: PrincipalDep,
    services: ServicesDep,
):
    await services.notifications.register_device(
        principal.user_id,
        principal.family_id,
        payload.installation_id,
        payload.expo_push_token,
        payload.platform,
    )
    return {"registered": True}


@router.delete("/api/v1/push/devices", status_code=204)
async def unregister_push_device(
    payload: PushDeviceDelete,
    principal: PrincipalDep,
    services: ServicesDep,
):
    await services.notifications.unregister_device(
        principal.user_id,
        principal.family_id,
        payload.installation_id,
    )
    return Response(status_code=204)
