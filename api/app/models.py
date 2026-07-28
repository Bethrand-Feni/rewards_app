from typing import Literal

from pydantic import BaseModel, Field


class ParentRegister(BaseModel):
    family_name: str = Field(min_length=2, max_length=60)
    display_name: str = Field(min_length=2, max_length=60)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)


class ParentLogin(BaseModel):
    email: str
    password: str


class ChildLogin(BaseModel):
    family_code: str = Field(min_length=6, max_length=6)
    username: str = Field(min_length=2, max_length=24)
    pin: str = Field(pattern=r"^\d{4,6}$")


class RefreshRequest(BaseModel):
    refresh_token: str


class ChildCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=60)
    username: str = Field(min_length=2, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")
    pin: str = Field(pattern=r"^\d{4,6}$")


class PinReset(BaseModel):
    pin: str = Field(pattern=r"^\d{4,6}$")


class ChoreWrite(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)
    suggested_points: int = Field(gt=0, le=100_000)
    mode: Literal["REUSABLE", "ONE_TIME"] = "REUSABLE"
    assigned_to_user_id: str | None = None


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

