export type Role = "PARENT" | "CHILD";

export type User = {
  user_id: string;
  family_id: string;
  role: Role;
  display_name: string;
  family_name: string;
  family_code: string;
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
  username: string;
  is_active: number;
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

