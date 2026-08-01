export type Role = "PARENT" | "CHILD";

export type User = {
  user_id: string;
  email: string;
  family_id: string | null;
  role: Role | null;
  display_name: string;
  family_name?: string;
  family_code?: string;
  timezone?: string;
  deletion_scheduled_for?: string | null;
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
};

export type Child = {
  id: string;
  display_name: string;
  claim_status: "WAITING" | "CLAIMED";
  join_pin_expires_at?: string | null;
  is_active: number;
  deletion_scheduled_for?: string | null;
};

export type HouseholdMember = {
  id: string;
  display_name: string;
  role: Role;
  joined_at: string;
  account_type: "ACCOUNT" | "CHILD_PROFILE";
  is_active: number;
  deletion_scheduled_for?: string | null;
};

export type HouseholdInvite = {
  family_name: string;
  family_code: string;
  join_pin: string;
  role: Role;
  expires_at: string;
};

export type Chore = {
  id: string;
  title: string;
  description: string;
  suggested_points: number;
  mode: "REUSABLE" | "ONE_TIME";
  assigned_to_user_id: string | null;
  assigned_to_name?: string | null;
  state: "ACTIVE" | "LOCKED" | "COMPLETED" | "INACTIVE";
  schedule_type: "NONE" | "DAILY" | "WEEKDAYS" | "WEEKENDS" | "WEEKLY" | "MONTHLY";
  start_date: string | null;
  due_local_time: string | null;
  weekday_mask: number;
  reminders_enabled: number;
  occurrence_id?: string | null;
  due_at?: string | null;
  local_due_date?: string | null;
  occurrence_status?: "OPEN" | "OVERDUE" | null;
  next_due_at?: string | null;
  next_occurrence_status?: "OPEN" | "OVERDUE" | null;
  display_title?: string;
  display_description?: string;
  display_points?: number;
};

export type Submission = {
  id: string;
  child_user_id: string;
  child_name: string;
  chore_id: string | null;
  submission_type: "CHORE" | "OTHER_ACTIVITY";
  title: string;
  description: string;
  status: "PENDING" | "APPROVED" | "REJECTED" | "CHANGES_REQUESTED";
  current_revision: number;
  awarded_points: number | null;
  review_comment: string | null;
  suggested_points: number | null;
  created_at: string;
};

export type Reward = {
  id: string;
  name: string;
  description: string;
  point_cost: number;
  is_active: number;
  has_image?: boolean;
};

export type Redemption = {
  id: string;
  reward_id: string;
  reward_name: string;
  child_name: string;
  child_user_id: string;
  point_cost_snapshot: number;
  status: "PENDING" | "APPROVED" | "REJECTED";
  review_comment: string | null;
  created_at: string;
};

export type PointTransaction = {
  id: string;
  transaction_type: string;
  amount: number;
  reason: string;
  created_at: string;
};
