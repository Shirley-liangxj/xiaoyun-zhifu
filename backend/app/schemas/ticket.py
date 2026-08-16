"""工单 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
  """创建工单"""
  title: str = Field(..., min_length=1, max_length=200)
  description: str = Field(default="", max_length=2000)
  priority: str = Field(default="normal", description="优先级: low/normal/high/urgent")
  conversation_id: Optional[int] = Field(None, description="关联会话ID")


class TicketUpdate(BaseModel):
  """更新工单"""
  title: Optional[str] = Field(None, min_length=1, max_length=200)
  description: Optional[str] = Field(None, max_length=2000)
  status: Optional[str] = Field(None, description="状态: open/in_progress/resolved/closed")
  priority: Optional[str] = Field(None, description="优先级: low/normal/high/urgent")
  assignee_id: Optional[int] = Field(None, description="指派坐席ID")


class TicketOut(BaseModel):
  """工单输出"""
  id: int
  title: str
  description: str
  status: str
  priority: str
  conversation_id: Optional[int] = None
  assignee_id: Optional[int] = None
  assignee_name: Optional[str] = None
  customer_name: Optional[str] = None
  created_at: datetime
  updated_at: datetime

  class Config:
    from_attributes = True
