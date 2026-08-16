"""知识库文档模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
  from app.models.company import Company


class KnowledgeDoc(Base):
  """知识库文档表 - 售后知识条目"""

  __tablename__ = "knowledge_docs"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
  title: Mapped[str] = mapped_column(String(200), nullable=False, comment="文档标题")
  content: Mapped[str] = mapped_column(Text, nullable=False, comment="文档内容")
  category: Mapped[str] = mapped_column(String(50), default="通用", comment="分类")
  is_indexed: Mapped[bool] = mapped_column(default=False, comment="是否已向量化")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(
    DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
  )

  # 关联
  company: Mapped[Company] = relationship("Company", back_populates="knowledge_docs")
