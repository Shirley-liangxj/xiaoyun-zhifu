"""公司设置模型 - 机器人配置"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
  from app.models.company import Company


class CompanySettings(Base):
  """公司级机器人设置"""

  __tablename__ = "company_settings"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), unique=True, nullable=False)
  welcome_message: Mapped[str] = mapped_column(
    Text, default="您好！我是智能客服小云，有什么可以帮您的？", comment="欢迎语"
  )
  confidence_threshold: Mapped[float] = mapped_column(
    Float, default=0.4, comment="低于此置信度建议转人工"
  )
  auto_suggest: Mapped[bool] = mapped_column(default=True, comment="客户消息后自动生成AI建议")
  reject_message: Mapped[Optional[str]] = mapped_column(
    Text,
    default="抱歉，这个问题我需要为您转接人工客服，请稍候。",
    comment="低置信度拒答话术",
  )

  company: Mapped["Company"] = relationship("Company", back_populates="settings")
