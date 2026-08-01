const base = process.env.SMOKE_API_URL ?? "http://127.0.0.1:8787/api/v1";
const suffix = Date.now().toString(36);
const password = "LocalSmokePassword123!";

async function request(path, options = {}, token) {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${base}${path}`, { ...options, headers });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(`${options.method ?? "GET"} ${path}: ${response.status} ${JSON.stringify(body)}`);
  return body;
}

const account = await request("/auth/register", {
  method: "POST",
  body: JSON.stringify({
    display_name: "Smoke Parent",
    email: `smoke-${suffix}@example.test`,
    password,
  }),
});
const session = await request("/households", {
  method: "POST",
  body: JSON.stringify({
    family_name: `Smoke Family ${suffix}`,
    timezone: "Africa/Johannesburg",
  }),
}, account.access_token);
const token = session.access_token;

const childInvite = await request("/household/invites", {
  method: "POST",
  body: JSON.stringify({ role: "CHILD" }),
}, token);

const childAccount = await request("/auth/register", {
  method: "POST",
  body: JSON.stringify({
    display_name: "Invited Child",
    email: `smoke-child-${suffix}@example.test`,
    password,
  }),
});
const childSession = await request("/households/join", {
  method: "POST",
  body: JSON.stringify({
    family_code: childInvite.family_code,
    join_pin: childInvite.join_pin,
  }),
}, childAccount.access_token);
if (childSession.user.role !== "CHILD") {
  throw new Error(`Expected child invite role, got ${childSession.user.role}`);
}

const parentInvite = await request("/household/invites", {
  method: "POST",
  body: JSON.stringify({ role: "PARENT" }),
}, token);
const secondParentAccount = await request("/auth/register", {
  method: "POST",
  body: JSON.stringify({
    display_name: "Second Parent",
    email: `smoke-parent-two-${suffix}@example.test`,
    password,
  }),
});
const secondParentSession = await request("/households/join", {
  method: "POST",
  body: JSON.stringify({
    family_code: parentInvite.family_code,
    join_pin: parentInvite.join_pin,
  }),
}, secondParentAccount.access_token);
if (secondParentSession.user.role !== "PARENT") {
  throw new Error(`Expected parent invite role, got ${secondParentSession.user.role}`);
}

const tomorrow = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
const chore = await request("/chores", {
  method: "POST",
  body: JSON.stringify({
    title: "Scheduled smoke chore",
    description: "Validates recurrence fields",
    suggested_points: 15,
    mode: "REUSABLE",
    assigned_to_user_id: childSession.user.user_id,
    schedule_type: "WEEKLY",
    start_date: tomorrow,
    due_local_time: "18:00",
    weekday_mask: 0,
    reminders_enabled: true,
  }),
}, token);
await request(`/chores/${chore.id}`, {
  method: "PATCH",
  body: JSON.stringify({
    title: "Edited scheduled chore",
    description: "Future occurrences use this snapshot",
    suggested_points: 20,
    mode: "REUSABLE",
    assigned_to_user_id: childSession.user.user_id,
    schedule_type: "WEEKLY",
    start_date: tomorrow,
    due_local_time: "18:30",
    weekday_mask: 0,
    reminders_enabled: true,
  }),
}, token);
const childChores = await request("/chores", {}, childSession.access_token);
if (!childChores[0]?.occurrence_id || !childChores[0]?.due_at) {
  throw new Error("Scheduled chore was not materialized for the child");
}

const reward = await request("/rewards", {
  method: "POST",
  body: JSON.stringify({ name: "Smoke reward", description: "Before edit", point_cost: 40 }),
}, token);
await request(`/rewards/${reward.id}`, {
  method: "PATCH",
  body: JSON.stringify({ name: "Edited smoke reward", description: "After edit", point_cost: 45 }),
}, token);
const rewardImage = new FormData();
rewardImage.set(
  "image",
  new Blob(
    [new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])],
    { type: "image/png" },
  ),
  "reward.png",
);
await request(`/rewards/${reward.id}/image`, { method: "POST", body: rewardImage }, token);
const rewardImageResponse = await fetch(`${base}/rewards/${reward.id}/image`, {
  headers: { Authorization: `Bearer ${token}` },
});
if (!rewardImageResponse.ok || rewardImageResponse.headers.get("content-type") !== "image/png") {
  throw new Error("Reward image was not available after upload");
}

const proof = new FormData();
proof.set("submission_type", "CHORE");
proof.set("title", "Edited scheduled chore");
proof.set("description", "Local end-to-end proof");
proof.set("chore_id", chore.id);
proof.set("chore_occurrence_id", childChores[0].occurrence_id);
proof.set(
  "image",
  new Blob(
    [
      new Uint8Array([
        0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
        0x00, 0x00, 0x00, 0x00,
      ]),
    ],
    { type: "image/png" },
  ),
  "proof.png",
);
const submission = await request(
  "/submissions",
  { method: "POST", body: proof },
  childSession.access_token,
);
const pendingSubmissions = await request("/submissions/pending", {}, token);
if (!pendingSubmissions.some((item) => item.id === submission.id)) {
  throw new Error("Child submission was not visible in the parent review queue");
}
await request(
  `/submissions/${submission.id}/approve`,
  {
    method: "POST",
    body: JSON.stringify({ awarded_points: 60 }),
  },
  token,
);
const awardedBalance = await request(
  `/points/balance`,
  {},
  childSession.access_token,
);
if (awardedBalance.balance !== 60) {
  throw new Error(`Expected 60 awarded points, got ${awardedBalance.balance}`);
}

const redemption = await request(
  `/rewards/${reward.id}/redemptions`,
  { method: "POST" },
  childSession.access_token,
);
const pendingRedemptions = await request("/redemptions/pending", {}, token);
if (!pendingRedemptions.some((item) => item.id === redemption.id)) {
  throw new Error("Child reward request was not visible to the parent");
}
await request(
  `/redemptions/${redemption.id}/approve`,
  {
    method: "POST",
    body: JSON.stringify({ comment: "Enjoy it" }),
  },
  token,
);
const finalBalance = await request(
  `/points/balance`,
  {},
  childSession.access_token,
);
if (finalBalance.balance !== 15) {
  throw new Error(`Expected 15 remaining points, got ${finalBalance.balance}`);
}

await request(`/household/children/${childSession.user.user_id}/deletion`, {
  method: "POST",
}, token);
await request(`/household/children/${childSession.user.user_id}/deletion/cancel`, { method: "POST" }, token);

await request("/account/deletion", {
  method: "POST",
  body: JSON.stringify({ family_name: `Smoke Family ${suffix}`, password }),
}, token);
await request("/account/deletion/cancel", { method: "POST" }, token);

const [children, members, chores, rewards] = await Promise.all([
  request("/household/children", {}, token),
  request("/household/members", {}, token),
  request("/chores", {}, token),
  request("/rewards", {}, token),
]);

console.log(JSON.stringify({
  family_id: session.user.family_id,
  children: children.length,
  members: members.length,
  chores: chores.length,
  rewards: rewards.length,
  child_account_name: children[0]?.display_name,
  edited_chore: chores[0]?.title,
  edited_reward: rewards[0]?.name,
  reward_has_image: rewards[0]?.has_image,
  child_occurrence_materialized: Boolean(childChores[0]?.occurrence_id),
  submission_visible_to_parent: true,
  reward_request_visible_to_parent: true,
  final_child_balance: finalBalance.balance,
}, null, 2));
