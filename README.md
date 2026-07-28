# Sibling Rewards

An Android-first Expo prototype for a household rewards loop:

1. A parent creates child profiles and chores.
2. A child signs in with a household code, username and PIN.
3. The child submits photographic proof.
4. The parent reviews the activity and awards points.
5. The child requests rewards and points are deducted on approval.

The repository contains:

- `mobile/` — Expo SDK 57, Expo Router, TypeScript and TanStack Query.
- `api/` — FastAPI on Cloudflare Python Workers with D1 and R2.
- `api/migrations/` — the complete D1 schema and integrity constraints.

## Prerequisites

- Node.js 22+
- npm 10+
- Python 3.13+
- `uv` 0.8.10 or newer (required by the current `pywrangler`)
- A Cloudflare account for remote D1/R2 deployment
- Expo Go on an Android phone

## Mobile setup

```bash
npm install
cp mobile/.env.example mobile/.env
```

The development API is provisioned at
`https://sibling-rewards-api-dev.chiboyfeni.workers.dev`, and `mobile/.env`
already points Expo to its `/api/v1` routes. Start Expo with:

```bash
npm run mobile
```

Scan the QR code using Expo Go. A real phone cannot use the default
`127.0.0.1` API URL to reach a Worker running on the computer.

## API setup

```bash
cd api
uv sync
cp .dev.vars.example .dev.vars
```

Replace both example secrets in `.dev.vars` with independent random values.

Create Cloudflare resources:

```bash
uv run pywrangler d1 create sibling-rewards-dev
uv run pywrangler r2 bucket create sibling-rewards-dev
```

Copy the returned D1 ID into `api/wrangler.jsonc`, then apply the migration:

```bash
uv run pywrangler d1 migrations apply sibling-rewards-dev --local
uv run pywrangler dev
```

For an Expo Go device, deploy the development Worker:

```bash
uv run pywrangler d1 migrations apply sibling-rewards-dev --remote
uv run pywrangler deploy
```

Cloudflare Python Workers are currently beta. The code deliberately uses only
FastAPI, the standard library and native Worker bindings to minimize package
compatibility risk.

## Verification

```bash
npm run mobile:check
cd api
uv run pytest
uv run python -m py_compile app/*.py
```

The end-to-end acceptance path is:

1. Register the parent and household.
2. Create a child profile, chore and reward.
3. Log out and sign in as the child using the displayed household code.
4. Submit the chore with a photo.
5. Sign back in as the parent and approve it.
6. Sign in as the child, confirm the ledger balance and request the reward.
7. Approve the redemption as the parent and confirm the deduction.

## Prototype boundaries

This version intentionally excludes additional adult admins, child email
accounts, recurring schedules, reward inventory, push notifications, offline
writes, password-recovery email, signed Android builds and store publishing.
