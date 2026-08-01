from __future__ import annotations

from fastapi import APIRouter, Response

from app.dependencies import PrincipalDep, ServicesDep
from app.models import (
    AccountLogin,
    AccountRegister,
    GoogleAuth,
    RefreshRequest,
)


router = APIRouter()


@router.post("/api/v1/auth/google/nonce")
async def create_google_nonce(services: ServicesDep):
    return await services.auth.create_google_nonce()


@router.post("/api/v1/auth/google")
async def login_google(payload: GoogleAuth, services: ServicesDep):
    return await services.auth.login_google(payload)


@router.post("/api/v1/auth/register", status_code=201)
async def register_account(
    payload: AccountRegister, services: ServicesDep
):
    return await services.auth.register_account(payload)


@router.post("/api/v1/auth/login")
async def login_account(payload: AccountLogin, services: ServicesDep):
    return await services.auth.login_account(payload)


@router.post("/api/v1/auth/refresh")
async def refresh(payload: RefreshRequest, services: ServicesDep):
    return await services.auth.refresh(payload.refresh_token)


@router.post("/api/v1/auth/logout", status_code=204)
async def logout(payload: RefreshRequest, services: ServicesDep):
    await services.auth.logout(payload.refresh_token)
    return Response(status_code=204)


@router.get("/api/v1/auth/me")
async def me(principal: PrincipalDep, services: ServicesDep):
    return await services.auth.me(principal)


@router.post("/api/v1/realtime/ticket")
async def realtime_ticket(
    principal: PrincipalDep, services: ServicesDep
):
    return services.auth.realtime_ticket(principal)
