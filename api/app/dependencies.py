from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request

from app.db import Database
from app.errors import AuthenticationFailed
from app.repositories.auth import AuthRepository
from app.repositories.children import ChildRepository
from app.repositories.chores import ChoreRepository
from app.repositories.deletions import DeletionRepository
from app.repositories.families import FamilyRepository
from app.repositories.household_invites import HouseholdInviteRepository
from app.repositories.notifications import NotificationRepository
from app.repositories.points import PointRepository
from app.repositories.rewards import RewardRepository
from app.repositories.submissions import SubmissionRepository
from app.security import Principal
from app.services.auth_service import AuthService
from app.services.chore_service import ChoreService
from app.services.deletion_service import DeletionService
from app.services.household_service import HouseholdService
from app.services.notification_service import NotificationService
from app.services.points_service import PointsService
from app.services.reward_service import RewardService
from app.services.scheduler_service import SchedulerService
from app.services.submission_service import SubmissionService


@dataclass
class Services:
    auth: AuthService
    household: HouseholdService
    chores: ChoreService
    submissions: SubmissionService
    points: PointsService
    rewards: RewardService
    notifications: NotificationService
    deletions: DeletionService
    scheduler: SchedulerService


def build_services(env) -> Services:
    db = Database(env.DB)
    auth_repository = AuthRepository(db)
    families = FamilyRepository(db)
    children = ChildRepository(db)
    household_invites = HouseholdInviteRepository(db)
    chores = ChoreRepository(db)
    submissions = SubmissionRepository(db)
    points = PointRepository(db)
    rewards = RewardRepository(db)
    notification_repository = NotificationRepository(db)
    deletions_repository = DeletionRepository(db)

    notifications = NotificationService(db, notification_repository)
    auth = AuthService(db, env, auth_repository, families)
    deletions = DeletionService(
        db, env, deletions_repository, auth
    )
    chore_service = ChoreService(db, env, chores, children)
    scheduler = SchedulerService(
        env,
        chores,
        notification_repository,
        notifications,
        deletions,
    )
    chore_service.materialize = scheduler.materialize_occurrences
    return Services(
        auth=auth,
        household=HouseholdService(
            db, env, families, children, household_invites, auth
        ),
        chores=chore_service,
        submissions=SubmissionService(
            db,
            env,
            submissions,
            chores,
            points,
            notifications,
        ),
        points=PointsService(
            env, points, children, notifications
        ),
        rewards=RewardService(
            db, env, rewards, points, notifications
        ),
        notifications=notifications,
        deletions=deletions,
        scheduler=scheduler,
    )


async def get_services(request: Request) -> Services:
    services = request.scope.get("services")
    if services is None:
        services = build_services(request.scope["env"])
        request.scope["services"] = services
    return services


ServicesDep = Annotated[Services, Depends(get_services)]


async def current_principal(
    request: Request,
    services: ServicesDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationFailed()
    return await services.auth.resolve_principal(
        authorization.removeprefix("Bearer ").strip(),
        request.url.path,
    )


PrincipalDep = Annotated[Principal, Depends(current_principal)]
