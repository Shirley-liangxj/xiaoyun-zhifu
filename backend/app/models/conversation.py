"""会话与消息模型"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
  from app.models.company import Company
  from app.models.ticket import Ticket
  from app.models.user import User


class Conversation(Base):
  """会话表 - 一次客户咨询对话"""

  __tablename__ = "conversations"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
  customer_name: Mapped[str] = mapped_column(String(50), default="客户", comment="客户昵称")
  channel: Mapped[str] = mapped_column(String(20), default="web", comment="渠道: web/wechat/phone")
  status: Mapped[str] = mapped_column(
    String(20), default="active", comment="状态: active/closed"
  )
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

  # 关联
  company: Mapped[Company] = relationship("Company", back_populates="conversations")
  messages: Mapped[List[Message]] = relationship("Message", back_populates="conversation")
  tickets: Mapped[List[Ticket]] = relationship("Ticket", back_populates="conversation")


class Message(Base):
  """消息表 - 会话中的单条消息"""

  __tablename__ = "messages"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)
  sender_id: Mapped[Optional[int]] = mapped_column(
    ForeignKey("users.id"), nullable=True, comment="坐席ID，客户消息为null"
  )
  role: Mapped[str] = mapped_column(
    String(20), nullable=False, comment="角色: customer/agent/ai_suggestion"
  )
  content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
  # AI 建议相关字段（阶段B使用）
  confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="AI置信度")
  sources: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="RAG来源JSON")
  is_sent: Mapped[bool] = mapped_column(default=False, comment="AI建议是否已发送")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  # 关联
  conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")
  sender: Mapped[Optional[User]] = relationship("User", back_populates="messages")
