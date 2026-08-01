from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.dependencies import PrincipalDep, ServicesDep
from app.models import RedemptionReview, ReviewComment, ReviewSubmission
from app.services.submission_service import MAX_IMAGE_BYTES


router = APIRouter()


@router.post("/api/v1/submissions", status_code=201)
async def create_submission(
    principal: PrincipalDep,
    services: ServicesDep,
    submission_type: Annotated[str, Form()],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    chore_id: Annotated[str | None, Form()] = None,
    chore_occurrence_id: Annotated[str | None, Form()] = None,
    image: UploadFile = File(...),
):
    services.auth.require_role(principal, "CHILD")
    return await services.submissions.create(
        principal.family_id,
        principal.user_id,
        principal.display_name,
        submission_type,
        title,
        description,
        chore_id,
        chore_occurrence_id,
        await image.read(MAX_IMAGE_BYTES + 1),
        image.content_type or "",
    )


@router.get("/api/v1/submissions/mine")
async def my_submissions(
    principal: PrincipalDep, services: ServicesDep
):
    services.auth.require_role(principal, "CHILD")
    return await services.submissions.list_mine(
        principal.family_id, principal.user_id
    )


@router.get("/api/v1/submissions/pending")
async def pending_submissions(
    principal: PrincipalDep, services: ServicesDep
):
    services.auth.require_role(principal, "PARENT")
    return await services.submissions.list_pending(principal.family_id)


@router.get("/api/v1/submissions/{submission_id}/image")
async def submission_image(
    submission_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
):
    content, content_type = await services.submissions.image(
        principal.family_id,
        principal.user_id,
        principal.role,
        submission_id,
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("/api/v1/submissions/{submission_id}/resubmit")
async def resubmit(
    submission_id: str,
    principal: PrincipalDep,
    services: ServicesDep,
    description: Annotated[str, Form()] = "",
    image: UploadFile = File(...),
):
    services.auth.require_role(principal, "CHILD")
    return await services.submissions.resubmit(
        principal.family_id,
        principal.user_id,
        principal.display_name,
        submission_id,
        description,
        await image.read(MAX_IMAGE_BYTES + 1),
        image.content_type or "",
    )


@router.post("/api/v1/submissions/{submission_id}/approve")
async def approve_submission(
    submission_id: str,
    payload: ReviewSubmission,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.submissions.approve(
        principal.family_id,
        principal.user_id,
        submission_id,
        payload.awarded_points,
    )


@router.post("/api/v1/submissions/{submission_id}/reject")
async def reject_submission(
    submission_id: str,
    payload: RedemptionReview,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.submissions.finish_review(
        principal.family_id,
        principal.user_id,
        submission_id,
        "REJECTED",
        payload.comment,
    )


@router.post(
    "/api/v1/submissions/{submission_id}/request-changes"
)
async def request_submission_changes(
    submission_id: str,
    payload: ReviewComment,
    principal: PrincipalDep,
    services: ServicesDep,
):
    services.auth.require_role(principal, "PARENT")
    return await services.submissions.finish_review(
        principal.family_id,
        principal.user_id,
        submission_id,
        "CHANGES_REQUESTED",
        payload.comment,
    )
