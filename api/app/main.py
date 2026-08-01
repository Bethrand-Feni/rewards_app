from __future__ import annotations

import importlib
import sys
import types
from urllib.parse import parse_qs, urlencode, urlparse

import asgi
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from workers import Response as WorkerResponse
from workers import WorkerEntrypoint

if __package__ in (None, ""):
    # Python Workers uploads the entrypoint directory as the module root. The
    # aliases preserve normal ``app.*`` package imports without duplicating
    # import logic throughout every layer.
    app_package = types.ModuleType("app")
    app_package.__path__ = []
    sys.modules.setdefault("app", app_package)
    for module_name in (
        "db",
        "errors",
        "models",
        "security",
        "scheduling",
        "realtime_contract",
    ):
        sys.modules[f"app.{module_name}"] = importlib.import_module(
            module_name
        )
    for package_name in ("repositories", "services", "routes"):
        sys.modules[f"app.{package_name}"] = importlib.import_module(
            package_name
        )

try:
    from dependencies import build_services
    from errors import AppError, AuthenticationFailed
    from realtime import HouseholdRealtime
    sys.modules["app.dependencies"] = sys.modules["dependencies"]
    from routes import (
        auth,
        chores,
        deletions,
        household,
        notifications,
        points,
        rewards,
        submissions,
    )
    from security import decode_access_token
    from services.common import env_value
except ImportError:
    from app.dependencies import build_services
    from app.errors import AppError, AuthenticationFailed
    from app.realtime import HouseholdRealtime
    from app.routes import (
        auth,
        chores,
        deletions,
        household,
        notifications,
        points,
        rewards,
        submissions,
    )
    from app.security import decode_access_token
    from app.services.common import env_value


app = FastAPI(title="Sibling Rewards API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    household.router,
    chores.router,
    submissions.router,
    points.router,
    rewards.router,
    notifications.router,
    deletions.router,
):
    app.include_router(router)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    headers = (
        {"WWW-Authenticate": "Bearer"}
        if isinstance(exc, AuthenticationFailed)
        else None
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sibling-rewards-api"}


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = urlparse(request.url)
        if url.path != "/api/v1/realtime":
            return await asgi.fetch(app, request, self.env)
        if (request.headers.get("Upgrade") or "").casefold() != "websocket":
            return WorkerResponse(
                "Expected a WebSocket upgrade", status=426
            )
        ticket = parse_qs(url.query).get("ticket", [""])[0]
        try:
            claims = decode_access_token(
                ticket, env_value(self.env, "JWT_SECRET")
            )
            if claims.get("purpose") != "realtime":
                raise ValueError("Invalid ticket purpose")
            principal = await build_services(
                self.env
            ).auth.resolve_principal(ticket, "/api/v1/realtime")
        except (ValueError, AppError):
            return WorkerResponse(
                "Invalid or expired realtime ticket", status=401
            )
        stub = self.env.HOUSEHOLD_REALTIME.getByName(
            f"family:{principal.family_id}"
        )
        params = urlencode(
            {
                "familyId": principal.family_id,
                "userId": principal.user_id,
                "role": principal.role,
            }
        )
        return await stub.fetch(
            f"https://realtime.internal/connect?{params}",
            method="GET",
            headers={"Upgrade": "websocket"},
        )

    async def scheduled(self, controller, env, ctx):
        await build_services(env or self.env).scheduler.run()
