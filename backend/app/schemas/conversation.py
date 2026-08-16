"""会话与消息 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
  """创建会话"""
  customer_name: str = Field(default="客户", max_length=50)
  channel: str = Field(default="web", max_length=20)


class ConversationOut(BaseModel):
  """会话列表项"""
  id: int
  customer_name: str
  channel: str
  status: str
  created_at: datetime
  closed_at: Optional[datetime] = None
  message_count: int = 0
  last_message: Optional[str] = None

  class Config:
    from_attributes = True


class MessageCreate(BaseModel):
  """发送消息"""
  content: str = Field(..., min_length=1)
  role: str = Field(default="agent", description="角色: customer/agent")


class MessageOut(BaseModel):
  """消息输出"""
  id: int
  conversation_id: int
  sender_id: Optional[int] = None
  role: str
  content: str
  confidence: Optional[float] = None
  sources: Optional[str] = None
  is_sent: bool
  created_at: datetime

  class Config:
    from_attributes = True


class ConversationDetail(ConversationOut):
  """会话详情（含消息列表）"""
  messages: list[MessageOut] = []


class AcceptSuggestionRequest(BaseModel):
  """采纳 AI 建议请求（可编辑内容）"""
  content: Optional[str] = Field(None, description="编辑后的内容，为空则使用原建议")


class AiSuggestionOut(BaseModel):
  """AI 建议输出"""
  id: int
  content: str
  confidence: float
  sources: list[dict] = []
  created_at: datetime

  class Config:
    from_attributes = True
