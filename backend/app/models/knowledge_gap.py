"""知识缺口模型 - 记录未命中或低置信度问题"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
  from app.models.company import Company


class KnowledgeGap(Base):
  """知识缺口表 - 系统未能有效回答的问题"""

  __tablename__ = "knowledge_gaps"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
  question: Mapped[str] = mapped_column(Text, nullable=False, comment="用户问题")
  hit_count: Mapped[int] = mapped_column(Integer, default=1, comment="出现次数")
  status: Mapped[str] = mapped_column(
    String(20), default="pending", comment="pending/resolved/ignored"
  )
  suggested_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="补充答案")
  last_confidence: Mapped[Optional[float]] = mapped_column(nullable=True, comment="最近置信度")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  company: Mapped["Company"] = relationship("Company", back_populates="knowledge_gaps")
