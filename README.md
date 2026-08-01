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
- An Android device or Android emulator
- An Expo development build (Google sign-in and remote push do not run in Expo Go)

### Start the app

From the repository root:

```bash
npm install
cp mobile/.env.example mobile/.env
```

Set `mobile/.env` to the shared development API:

```env
EXPO_PUBLIC_API_URL=<shared-development-api-url>/api/v1
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=<google-web-oauth-client-id>
```

Ask a project maintainer for the current URL. It is shared privately and is not
committed to this repository.

Start Metro for an installed development build:

```bash
npm run mobile
```

Open the development build on the device or emulator. To build one locally,
run `npm --workspace mobile run android:dev`. An EAS development APK can be
built with `npm --workspace mobile run build:android:dev`.

The development API and its test data are shared with the project team. Do not
use real names, email addresses, PINs, passwords, or sensitive photos in test
accounts.

Passwords must contain at least 10 characters. Every person signs in with an
email and password, or with Google. A child’s one-time join PIN contains six
digits and expires after 24 hours.

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

1. A person creates an account with an email, password, and display name.
2. A parent creates a household, then adds child profiles, chores, and rewards.
3. A child creates or signs in to their own account, then connects it to the
   child profile using the household code and one-time join PIN.
4. The child selects a chore and submits photo proof.
5. The parent reviews the submission and awards points.
6. The child requests an affordable reward.
7. The parent approves or rejects the reward request.
8. Approved rewards deduct their point cost from the child’s balance.

Chores can also be scheduled once, daily, or on selected weekdays. Scheduled
chores show their due time and overdue status; the first child to submit an
“Everyone” occurrence claims that occurrence.

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

1. Create an account, then create a household.
2. Create a child profile and record its one-time join PIN, then create a chore
   and reward.
3. Sign out, create the child’s email account, and connect it using the
   household code and one-time join PIN.
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

## External service setup

Google sign-in requires Android and Web OAuth clients in Google Cloud. The
Android client must use package `com.chiboyfeni.siblingrewards` and the SHA-1
of each development/production signing key. Put the Web client ID in
`mobile/.env` and set the matching client ID as `GOOGLE_WEB_CLIENT_ID` on the
Worker. Google sign-in auto-links a verified email to an existing account.

Push notifications require an EAS project ID and Android FCM v1 credentials.
After running `eas init`, keep the generated project ID in the Expo config and
upload the FCM service account through EAS credentials. The Settings screen
explains permission before Android displays its system prompt.

The Worker cron runs every five minutes to materialize scheduled chores, mark
overdue work, enqueue reminders, and retry notifications. Account and child
deletions have a 30-day recovery window. Physical purge remains disabled in
development until `DELETION_PURGE_ENABLED=true` is deliberately set after a
backup/restore rehearsal.

## Current boundaries

The app still has one parent account per household and no password-recovery
email provider. Google sign-in is the alternate access avenue for linked
accounts. Additional adult administrators, reward inventory, offline writes,
iOS release configuration, and Play Store publishing remain outside this
phase.
