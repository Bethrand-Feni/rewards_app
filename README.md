# Sibling Rewards

Private MVP repository for an Android-first household rewards app.

Parents create child profiles, chores, and rewards. Children submit photo proof
of completed activities, earn points when a parent approves them, and request
rewards using their balance.

## Quick setup — use the shared development API

This is the recommended setup for day-to-day mobile development and
end-to-end testing.

### Requirements

- Node.js 22+
- npm 10+
- Expo Go on an Android device or Android emulator

### Start the app

From the repository root:

```bash
npm install
cp mobile/.env.example mobile/.env
```

Set `mobile/.env` to the shared development API:

```env
EXPO_PUBLIC_API_URL=<shared-development-api-url>/api/v1
```

Ask a project maintainer for the current URL. It is shared privately and is not
committed to this repository.

Start Expo:

```bash
npm run mobile
```

Open the app with Expo Go or an Android emulator.

The development API and its test data are shared with the project team. Do not
use real names, email addresses, PINs, passwords, or sensitive photos in test
accounts.

Parent passwords must contain at least 10 characters. Child PINs must contain
4–6 digits.

### Android emulator networking

An emulator can normally reach the shared HTTPS API directly. If the emulator
cannot resolve internet hostnames, restart its network or cold boot the
emulator before changing application code.

When testing an API running on the same computer, use Android Debug Bridge
port forwarding:

```bash
adb reverse tcp:8787 tcp:8787
```

The mobile app can then use `http://127.0.0.1:8787/api/v1`.

## Core flow

1. A parent creates a household and account.
2. The parent creates child profiles, chores, and rewards.
3. A child signs in with the household code, username, and PIN.
4. The child selects a chore and submits photo proof.
5. The parent reviews the submission and awards points.
6. The child requests an affordable reward.
7. The parent approves or rejects the reward request.
8. Approved rewards deduct their point cost from the child’s balance.

## Verification

Run the mobile TypeScript check from the repository root:

```bash
npm run mobile:check
```

Run the API tests:

```bash
cd api
uv run pytest
uv run python -m py_compile app/*.py
```

### End-to-end acceptance path

1. Create a parent account and household.
2. Create a child profile, chore, and reward.
3. Sign out and sign in as the child.
4. Open the chore and submit it with a non-sensitive test photo.
5. Sign in as the parent and approve the submission.
6. Sign in as the child and confirm the awarded balance.
7. Request a reward.
8. Approve the request as the parent.
9. Confirm the reward cost was deducted and both queues are empty.

Photo proof is stored in the development R2 bucket. Test account and ledger
data are stored in the development D1 database.

## Optional — run the API locally

Use this setup when changing the API or validating backend work before a
deployment.

### Requirements

- Python 3.13+
- `uv` 0.8.10+
- Cloudflare account access for remote D1/R2 work

From the repository root:

```bash
cd api
uv sync
cp .dev.vars.example .dev.vars
```

Replace the example values in `.dev.vars` with two independent, long, random
secrets. Never commit `.dev.vars`.

Apply the D1 schema locally and start the Worker:

```bash
uv run pywrangler d1 migrations apply sibling-rewards-dev --local
uv run pywrangler dev
```

Set the mobile environment while testing the local API:

```env
EXPO_PUBLIC_API_URL=http://127.0.0.1:8787/api/v1
```

A physical phone cannot use `127.0.0.1` to reach your computer. Use the shared
development API, or expose the local API through a secure development tunnel.

Cloudflare Python Workers are currently beta. The API intentionally limits its
dependencies and uses native D1 and R2 bindings to reduce runtime
compatibility risk.

## Repository structure

- `mobile/` — Expo SDK 57, Expo Router, React Native, TypeScript, and TanStack
  Query.
- `api/` — FastAPI running on Cloudflare Python Workers.
- `api/migrations/` — D1 schema, indexes, and integrity constraints.
- `api/tests/` — backend tests.

## MVP boundaries

The MVP intentionally excludes additional adult administrators, child email
accounts, recurring schedules, reward inventory, push notifications, offline
writes, password-recovery email, signed Android builds, and Play Store
publishing.
