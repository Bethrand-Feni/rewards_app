# Sibling Rewards API — Service/Repository Refactor Handover

## Objective

Refactor the Python FastAPI backend into a lightweight Service/Repository
architecture while retaining:

- Native Cloudflare D1 bindings.
- Explicit, hand-written SQL.
- Existing FastAPI endpoint paths and response contracts.
- Existing Cloudflare Worker, R2, Durable Object, cron, and real-time behavior.

Do not introduce SQLAlchemy, an ORM, or a generic repository.

The purpose of the refactor is organization and testability, not abstraction
for its own sake.

## Important implementation constraint

Cloudflare D1 does not provide a traditional interactive transaction spanning
multiple awaited repository calls. Workflows that must be atomic must construct
prepared statements and submit them through `D1Database.batch()`.

Repositories own the SQL and construct batch statements. Services decide which
domain operations belong in a batch. Services must never contain SQL.

## Target structure

```text
api/app/
├── main.py
├── db.py
├── dependencies.py
├── errors.py
├── models.py
├── security.py
├── realtime.py
├── realtime_contract.py
├── scheduling.py
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   ├── household.py
│   ├── chores.py
│   ├── submissions.py
│   ├── points.py
│   ├── rewards.py
│   ├── notifications.py
│   └── deletions.py
├── repositories/
│   ├── __init__.py
│   ├── auth.py
│   ├── families.py
│   ├── children.py
│   ├── chores.py
│   ├── submissions.py
│   ├── points.py
│   ├── rewards.py
│   ├── notifications.py
│   └── deletions.py
└── services/
    ├── __init__.py
    ├── auth_service.py
    ├── household_service.py
    ├── chore_service.py
    ├── submission_service.py
    ├── points_service.py
    ├── reward_service.py
    ├── notification_service.py
    ├── deletion_service.py
    └── scheduler_service.py
```

Keep `models.py` as one module during the initial refactor. It may become a
domain-organized `models/` package later if its size becomes difficult to
manage, but that is not required for this work.

## Layer responsibilities

### `main.py`

`main.py` should only:

- Create and configure FastAPI.
- Register middleware and application exception handlers.
- Include routers.
- Define the Cloudflare `WorkerEntrypoint`.
- Delegate WebSocket upgrades to the real-time implementation.
- Delegate scheduled events to `SchedulerService`.

No application SQL or business workflows should remain in `main.py`.

### Routes

Routes:

- Validate HTTP input through Pydantic models.
- Resolve the authenticated principal.
- Enforce coarse role requirements such as parent-only or child-only.
- Call one service method.
- Return the appropriate response and HTTP status.

Routes must not:

- Execute or construct SQL.
- Import repositories.
- Coordinate multiple persistence operations.
- Enqueue notifications directly.
- Implement resource ownership or state-transition rules.

### Services

Services:

- Implement business rules and workflows.
- Enforce household ownership and child ownership.
- Enforce valid resource-state transitions.
- Coordinate repositories.
- Construct atomic workflows from repository-produced statements.
- Trigger real-time and notification behavior at the appropriate workflow
  boundary.

Services accept explicit values such as `family_id`, `user_id`, and role. They
must not depend directly on FastAPI `Request` or raise `HTTPException`.

### Repositories

Repositories:

- Contain all application SQL for their domain.
- Bind D1 parameters.
- Convert rows into record models.
- Expose domain-specific reads and writes.
- Produce `DbStatement` values for atomic multi-repository batches.

Use descriptive methods such as:

- `find_by_id(...)`
- `list_available_for_child(...)`
- `list_pending_for_family(...)`
- `mark_occurrence_submitted_statement(...)`
- `approve_statement(...)`
- `deactivate(...)`

Do not create methods that accept arbitrary table names, columns, filters, or
raw request data.

Every family-owned resource query must include `family_id` in its predicate,
even when IDs are globally unique.

## Database wrapper

Create `api/app/db.py` as the only place that handles repeated D1 result and
JavaScript-to-Python conversion boilerplate.

Recommended public interface:

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DbStatement:
    sql: str
    params: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ExecuteResult:
    changes: int


class Database:
    def __init__(self, binding):
        self._binding = binding

    async def one(self, sql: str, *params: Any) -> dict[str, Any] | None:
        ...

    async def many(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        ...

    async def execute(self, sql: str, *params: Any) -> ExecuteResult:
        ...

    async def batch(
        self,
        statements: list[DbStatement],
    ) -> list[ExecuteResult]:
        ...
```

Repositories may call `one()`, `many()`, and `execute()` for independent
operations. For an atomic cross-domain workflow, repositories return
`DbStatement` objects and the service passes them to `Database.batch()`.

Example:

```python
statements = [
    submissions.approve_statement(...),
    points.award_statement(...),
    occurrences.complete_statement(...),
    notifications.enqueue_statement(...),
]

results = await db.batch(statements)
```

Inspect affected-row counts after conditional state transitions so a stale or
racing request cannot report success.

## SQL conventions

All extracted or newly written SQL must follow these rules:

- Use numbered placeholders: `?1`, `?2`, and so on.
- Never interpolate request values into SQL.
- Keep SQL as named constants beside the repository methods that use it.
- Avoid `SELECT *` for API-facing reads.
- Use `LIMIT 1` for single-row lookups.
- Make ordering deterministic.
- Add schema and index changes only through migrations.
- Never accept dynamic table or column names from request data.
- Prefer conditional writes for state transitions.
- Use D1 batches for atomic multi-write workflows.

Example:

```python
FIND_CHORE = """
SELECT
  id,
  family_id,
  title,
  description,
  suggested_points,
  state,
  schedule_type,
  assigned_to_user_id
FROM chores
WHERE id = ?1
  AND family_id = ?2
LIMIT 1
"""
```

## Authorization boundary

Authorization is divided between layers:

- Routes validate access tokens and enforce broad roles.
- Services verify household ownership, child ownership, assignment, balances,
  and allowed state transitions.
- Repositories execute explicitly family-scoped queries but do not decide
  policy.

This ensures that a valid resource ID alone can never authorize access.

## Application errors

Create framework-independent errors in `errors.py`, for example:

```python
class AppError(Exception):
    pass


class ResourceNotFound(AppError):
    pass


class Conflict(AppError):
    pass


class PermissionDenied(AppError):
    pass


class AuthenticationFailed(AppError):
    pass
```

Register FastAPI exception handlers in `main.py` to translate these into the
existing HTTP status codes and response format.

Services and repositories must not raise `HTTPException`.

## Dependency construction

Create request-scoped dependencies in `dependencies.py`.

One `Database` instance should wrap `request.scope["env"].DB`, and repositories
and services should be lightweight objects constructed around that instance.

An application container may expose:

```python
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
```

Do not create global repository or service instances because Cloudflare
bindings are supplied by the active Worker environment.

## Domain allocation

Use the following ownership boundaries:

- `auth`: users, Google identities, nonces, sessions, refresh, logout, login
  attempts.
- `families`: household profile, access code, timezone, parent membership.
- `children`: child membership, PIN, edit, deactivate, scheduled deletion.
- `chores`: chores and chore occurrences.
- `submissions`: submissions, revisions, and submission-image metadata.
- `points`: point transactions and balances.
- `rewards`: rewards and reward redemptions.
- `notifications`: push devices and notification outbox.
- `deletions`: deletion requests, purge selection, and purge statements.

R2 object operations remain in services because they coordinate storage and
database metadata. The database metadata SQL remains in repositories.

## Workflows that must remain atomic

At minimum, preserve atomic D1 batches for:

- Parent registration and household creation.
- Child profile creation.
- Chore submission and occurrence locking.
- Submission approval, occurrence completion, and point award.
- Reward approval and point deduction.
- Mutation and notification-outbox creation where consistency matters.
- Account or child deletion scheduling and session revocation.
- Physical deletion batches after R2 objects are removed.

If R2 succeeds and the D1 batch fails, the service must apply the existing
compensation behavior where possible.

## Real-time and scheduled work

Keep Durable Object real-time transport separate from repositories.

Services publish real-time events only after the relevant D1 operation
succeeds.

`SchedulerService` should coordinate:

- Chore occurrence materialization.
- Reminder and overdue state changes.
- Notification-outbox delivery and retry.
- Recoverable deletion purges when enabled.

The Cloudflare cron is configured as:

```cron
0 * * * *
```

This runs at minute zero of every hour in UTC.

Because the scheduler is hourly, a reminder defined as “one hour before” is
best-effort and may be delivered anywhere within the hourly processing window.
Do not describe it as exact-to-the-minute behavior. If exact reminder timing is
required later, restore a more frequent cron or use a different scheduling
mechanism.

## Testing strategy

### Repository integration tests

- Apply migrations to local D1.
- Verify repository reads and writes.
- Verify constraints and conditional updates.
- Verify batch rollback behavior.
- Verify family scoping.

### Service unit tests

- Use repository fakes or protocols.
- Verify business rules and state transitions.
- Verify the correct batch statements are selected.
- Verify real-time and notification actions occur only after persistence
  succeeds.

### Route tests

- Override service dependencies.
- Test authentication and role requirements.
- Test request validation.
- Test HTTP status and response mapping.

### Architecture checks

Add automated checks that:

- Routes do not import repositories.
- SQL keywords do not appear in route or service modules.
- Direct D1 binding operations do not appear outside `db.py`.
- Application SQL exists only in repositories and migrations.

## Incremental implementation order

Do not perform a single large move. Extract one domain at a time while keeping
the API operational:

1. Add `db.py`, `errors.py`, `dependencies.py`, package directories, and router
   registration.
2. Extract rewards and redemptions.
3. Extract children and household operations.
4. Extract chores and scheduled occurrences.
5. Extract points.
6. Extract submissions and R2 photo workflows.
7. Extract push notifications and scheduler behavior.
8. Extract authentication and recoverable deletion last because they affect
   session safety.
9. Remove obsolete helpers and remaining SQL from `main.py`.
10. Run the complete API and mobile verification suite.

After each domain:

- Preserve endpoint paths.
- Preserve request and response schemas.
- Run relevant tests.
- Confirm no SQL remains in that domain's old route implementation.

## Definition of done

The refactor is complete when:

- No application SQL remains in routes, services, or `main.py`.
- Only repositories use `Database.one()`, `many()`, and `execute()`.
- Services coordinate all multi-resource workflows.
- Atomic workflows use `Database.batch()`.
- Extracted SQL uses numbered parameters.
- Routes do not import repositories.
- Services and repositories do not raise FastAPI `HTTPException`.
- Existing API paths and mobile-facing response contracts remain compatible.
- Migrations apply successfully to an empty local database.
- Repository, service, route, scheduling, and real-time tests pass.
- The complete parent and child end-to-end flow passes.
- `main.py` contains only FastAPI and Cloudflare Worker wiring.
- No ORM or generic repository has been introduced.

## Safety notes for the implementer

- The worktree may already contain active feature work. Inspect `git status`
  before editing and preserve unrelated changes.
- Refactor behavior before changing behavior. Any functional correction found
  during extraction should receive a focused test and be documented separately.
- Do not deploy automatically merely because the refactor passes local tests.
  Validate migrations and the full mobile flow before changing the live Worker.
