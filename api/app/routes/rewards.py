from __future__ import annotations

from fastapi import APIRouter, File, Response, UploadFile

from app.dependencies import PrincipalDep, ServicesDep
from app.models import RedemptionReview, RewardWrite
from app.services.reward_service import RewardService


router = APIRouter()


@router.get("/api/v1/rewards")
async def list_rewards(
    principal: PrincipalDep, services: ServicesDep
):
    return await services.rewards.list_rewards(
        principal.family_id, principal.role
    )


@router.post("/api/v1/rewards", status_code=201)
async def create_reward(
    payload: RewardWrite,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.rewards.create_reward(
        principal.family_id, principal.user_id, payload
    )


@router.patch("/api/v1/rewards/{reward_id}")
async def update_reward(
    reward_id: str,
    payload: RewardWrite,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.rewards.update_reward(
        principal.family_id, reward_id, payload
    )


@router.post("/api/v1/rewards/{reward_id}/image")
async def upload_reward_image(
    reward_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
    image: UploadFile = File(...),
):
    services.auth.require_role(principal, "PARENT")
    return await services.rewards.upload_image(
        principal.family_id,
        reward_id,
        await image.read(RewardService.MAX_IMAGE_BYTES + 1),
        image.content_type or "",
    )


@router.get("/api/v1/rewards/{reward_id}/image")
async def reward_image(
    reward_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
):
    content, content_type = await services.rewards.image(
        principal.family_id, reward_id
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.delete("/api/v1/rewards/{reward_id}", status_code=204)
async def deactivate_reward(
    reward_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    await services.rewards.deactivate_reward(
        principal.family_id, reward_id
    )
    return Response(status_code=204)


@router.post(
    "/api/v1/rewards/{reward_id}/redemptions", status_code=201
)
async def request_redemption(
    reward_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "CHILD")
    return await services.rewards.request_redemption(
        principal.family_id,
        principal.user_id,
        principal.display_name,
        reward_id,
    )


@router.get("/api/v1/redemptions/mine")
async def my_redemptions(
    principal: PrincipalDep, services: ServicesDep
):
    services.auth.require_role(principal, "CHILD")
    return await services.rewards.list_mine(
        principal.family_id, principal.user_id
    )


@router.get("/api/v1/redemptions/pending")
async def pending_redemptions(
    principal: PrincipalDep, services: ServicesDep
):
    services.auth.require_role(principal, "PARENT")
    return await services.rewards.list_pending(principal.family_id)


@router.post("/api/v1/redemptions/{redemption_id}/approve")
async def approve_redemption(
    redemption_id: str,
    payload: RedemptionReview,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.rewards.approve(
        principal.family_id,
        principal.user_id,
        redemption_id,
        payload,
    )


@router.post("/api/v1/redemptions/{redemption_id}/reject")
async def reject_redemption(
    redemption_id: str,
    payload: RedemptionReview,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.rewards.reject(
        principal.family_id,
        principal.user_id,
        redemption_id,
        payload,
    )
