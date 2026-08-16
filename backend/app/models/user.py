"""用户模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
  from app.models.company import Company
  from app.models.conversation import Message
  from app.models.ticket import Ticket


class User(Base):
  """用户表 - 客服坐席账号"""

  __tablename__ = "users"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
  email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
  hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
  display_name: Mapped[str] = mapped_column(String(50), default="", comment="显示名称")
  role: Mapped[str] = mapped_column(String(20), default="agent", comment="角色: admin/agent")
  company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
  is_active: Mapped[bool] = mapped_column(default=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  # 关联
  company: Mapped[Company] = relationship("Company", back_populates="users")
  messages: Mapped[List[Message]] = relationship("Message", back_populates="sender")
  assigned_tickets: Mapped[List[Ticket]] = relationship("Ticket", back_populates="assignee")
