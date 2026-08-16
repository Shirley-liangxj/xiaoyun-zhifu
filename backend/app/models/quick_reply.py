"""快捷话术模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
  from app.models.company import Company


class QuickReply(Base):
  """快捷话术表 - 坐席常用回复模板"""

  __tablename__ = "quick_replies"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
  category: Mapped[str] = mapped_column(String(30), nullable=False, comment="分类")
  title: Mapped[str] = mapped_column(String(100), nullable=False, comment="话术标题")
  content: Mapped[str] = mapped_column(Text, nullable=False, comment="话术内容")
  use_count: Mapped[int] = mapped_column(Integer, default=0, comment="使用次数")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  company: Mapped["Company"] = relationship("Company", back_populates="quick_replies")
