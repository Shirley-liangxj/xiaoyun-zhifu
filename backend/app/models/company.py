"""公司（租户）模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
  from app.models.company_settings import CompanySettings
  from app.models.conversation import Conversation
  from app.models.knowledge import KnowledgeDoc
  from app.models.knowledge_gap import KnowledgeGap
  from app.models.quick_reply import QuickReply
  from app.models.ticket import Ticket
  from app.models.user import User


class Company(Base):
  """公司表 - 多租户隔离单位"""

  __tablename__ = "companies"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  name: Mapped[str] = mapped_column(String(100), nullable=False, comment="公司名称")
  industry: Mapped[str] = mapped_column(String(50), default="服饰", comment="行业类型")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  # 关联
  users: Mapped[List[User]] = relationship("User", back_populates="company")
  knowledge_docs: Mapped[List[KnowledgeDoc]] = relationship("KnowledgeDoc", back_populates="company")
  conversations: Mapped[List[Conversation]] = relationship("Conversation", back_populates="company")
  tickets: Mapped[List[Ticket]] = relationship("Ticket", back_populates="company")
  knowledge_gaps: Mapped[List[KnowledgeGap]] = relationship("KnowledgeGap", back_populates="company")
  quick_replies: Mapped[List[QuickReply]] = relationship("QuickReply", back_populates="company")
  settings: Mapped[Optional["CompanySettings"]] = relationship("CompanySettings", back_populates="company", uselist=False)
