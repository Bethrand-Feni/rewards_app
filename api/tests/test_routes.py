from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import current_principal, get_services
from app.routes import submissions
from app.security import Principal


class FakeAuth:
    def require_role(self, principal, role):
        assert principal.role == role


class FakeSubmissions:
    def __init__(self):
        self.family_id = None

    async def list_pending(self, family_id):
        self.family_id = family_id
        return [{"id": "submission-1", "status": "PENDING"}]


@dataclass
class FakeServices:
    auth: FakeAuth
    submissions: FakeSubmissions


def test_pending_submission_route_delegates_to_service() -> None:
    app = FastAPI()
    app.include_router(submissions.router)
    fake = FakeServices(FakeAuth(), FakeSubmissions())

    async def services_override():
        return fake

    async def principal_override():
        return Principal(
            user_id="parent-1",
            family_id="family-1",
            role="PARENT",
            display_name="Parent",
            email="parent@example.com",
        )

    app.dependency_overrides[get_services] = services_override
    app.dependency_overrides[current_principal] = principal_override

    response = TestClient(app).get("/api/v1/submissions/pending")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "submission-1", "status": "PENDING"}
    ]
    assert fake.submissions.family_id == "family-1"
