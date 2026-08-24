"""工单模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
  from app.models.company import Company
  from app.models.conversation import Conversation
  from app.models.user import User


class Ticket(Base):
  """工单表 - 售后问题跟踪"""

  __tablename__ = "tickets"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
  conversation_id: Mapped[Optional[int]] = mapped_column(
    ForeignKey("conversations.id"), nullable=True, comment="关联会话"
  )
  assignee_id: Mapped[Optional[int]] = mapped_column(
    ForeignKey("users.id"), nullable=True, comment="负责坐席"
  )
  title: Mapped[str] = mapped_column(String(200), nullable=False, comment="工单标题")
  description: Mapped[str] = mapped_column(Text, default="", comment="问题描述")
  status: Mapped[str] = mapped_column(
    String(20), default="open", comment="状态: open/in_progress/resolved/closed"
  )
  priority: Mapped[str] = mapped_column(
    String(10), default="normal", comment="优先级: low/normal/high/urgent"
  )
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(
    DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
  )

  # 关联
  company: Mapped[Company] = relationship("Company", back_populates="tickets")
  conversation: Mapped["Conversation | None"] = relationship(
    "Conversation", back_populates="tickets"
  )
  assignee: Mapped["User | None"] = relationship("User", back_populates="assigned_tickets")
