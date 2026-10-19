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
    String(20), default="pending", comment="pending/indexing_failed/resolved/ignored"
  )
  suggested_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="补充答案")
  knowledge_doc_id: Mapped[Optional[int]] = mapped_column(
    ForeignKey("knowledge_docs.id"), nullable=True, comment="用于解决缺口的知识文档"
  )
  resolution_version: Mapped[int] = mapped_column(Integer, default=0, comment="处理尝试版本")
  last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="最近索引失败原因")
  resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
  last_confidence: Mapped[Optional[float]] = mapped_column(nullable=True, comment="最近置信度")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  company: Mapped["Company"] = relationship("Company", back_populates="knowledge_gaps")
