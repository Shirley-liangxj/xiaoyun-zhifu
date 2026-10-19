"""结构化人工审核动作，替代进程内 JSON pending 状态。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HumanReviewAction(Base):
  __tablename__ = "human_review_actions"

  id: Mapped[str] = mapped_column(String(64), primary_key=True)
  company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
  conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
  customer_name: Mapped[str] = mapped_column(String(50), default="访客")
  action: Mapped[str] = mapped_column(String(50), nullable=False)
  title: Mapped[str] = mapped_column(String(100), nullable=False)
  detail: Mapped[str] = mapped_column(Text, default="")
  payload: Mapped[str] = mapped_column(Text, default="{}")
  status: Mapped[str] = mapped_column(String(30), default="pending_buyer", index=True)
  risk_reason: Mapped[str] = mapped_column(Text, default="")
  buyer_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
  reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  review_note: Mapped[str] = mapped_column(Text, default="")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class HumanReviewEvent(Base):
  """每次审核状态变化的审计记录。"""

  __tablename__ = "human_review_events"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
  action_id: Mapped[str] = mapped_column(ForeignKey("human_review_actions.id"), nullable=False, index=True)
  company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
  conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
  from_status: Mapped[str] = mapped_column(String(30), nullable=False)
  to_status: Mapped[str] = mapped_column(String(30), nullable=False)
  actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
  actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
  note: Mapped[str] = mapped_column(Text, default="")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
