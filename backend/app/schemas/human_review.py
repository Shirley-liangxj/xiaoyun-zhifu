"""人工审核单与审计事件 Schema。"""
from datetime import datetime

from pydantic import BaseModel, Field


class HumanReviewEventOut(BaseModel):
  id: int
  from_status: str
  to_status: str
  actor_type: str
  actor_id: int | None = None
  note: str = ""
  created_at: datetime

  class Config:
    from_attributes = True


class HumanReviewOut(BaseModel):
  id: str
  conversation_id: int
  customer_name: str
  action: str
  title: str
  detail: str = ""
  payload: dict = {}
  status: str
  risk_reason: str = ""
  buyer_confirmed_at: datetime | None = None
  reviewer_id: int | None = None
  reviewed_at: datetime | None = None
  review_note: str = ""
  created_at: datetime
  events: list[HumanReviewEventOut] = []


class HumanReviewDecision(BaseModel):
  decision: str = Field(..., pattern="^(approved|rejected|need_more_info)$")
  note: str = Field(default="", max_length=500)
