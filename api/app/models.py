from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class AccountRegister(BaseModel):
    display_name: str = Field(min_length=2, max_length=60)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)


class AccountLogin(BaseModel):
    email: str
    password: str


class HouseholdCreate(BaseModel):
    family_name: str = Field(min_length=2, max_length=60)
    timezone: str = Field(default="Africa/Johannesburg", min_length=1, max_length=64)


class HouseholdJoin(BaseModel):
    family_code: str = Field(min_length=6, max_length=6)
    join_pin: str = Field(pattern=r"^\d{6}$")


class HouseholdInviteCreate(BaseModel):
    role: Literal["PARENT", "CHILD"]


class RefreshRequest(BaseModel):
    refresh_token: str


class ChildCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=60)


class ChildUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=60)


class ChoreWrite(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)
    suggested_points: int = Field(gt=0, le=100_000)
    mode: Literal["REUSABLE", "ONE_TIME"] = "REUSABLE"
    assigned_to_user_id: str | None = None
    schedule_type: Literal[
        "NONE", "DAILY", "WEEKDAYS", "WEEKENDS", "WEEKLY", "MONTHLY"
    ] = "NONE"
    start_date: date | None = None
    due_local_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    weekday_mask: int = Field(default=0, ge=0, le=127)
    reminders_enabled: bool = True


class PushDeviceWrite(BaseModel):
    installation_id: str = Field(min_length=8, max_length=128)
    expo_push_token: str = Field(min_length=16, max_length=256)
    platform: Literal["ANDROID", "IOS"]


class PushDeviceDelete(BaseModel):
    installation_id: str = Field(min_length=8, max_length=128)


class FamilyDeletionCreate(BaseModel):
    family_name: str
    password: str | None = Field(default=None, max_length=128)
    google_id_token: str | None = None
    nonce: str | None = None


class GoogleAuth(BaseModel):
    id_token: str
    nonce: str


class ReviewSubmission(BaseModel):
    awarded_points: int = Field(gt=0, le=100_000)


class ReviewComment(BaseModel):
    comment: str = Field(min_length=2, max_length=500)


class AdjustmentCreate(BaseModel):
    child_user_id: str
    amount: int = Field(ge=-100_000, le=100_000)
    reason: str = Field(min_length=3, max_length=500)


class RewardWrite(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)
    point_cost: int = Field(gt=0, le=100_000)


class RedemptionReview(BaseModel):
    comment: str = Field(default="", max_length=500)
