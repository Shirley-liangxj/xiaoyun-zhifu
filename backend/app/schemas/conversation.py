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
  last_message_at: Optional[datetime] = None
  unread_count: int = 0

  class Config:
    from_attributes = True


class MessageCreate(BaseModel):
  """发送消息"""
  content: str = Field(..., min_length=1)
  role: str = Field(default="agent", description="角色: customer/agent")
  is_internal: bool = Field(default=False, description="内部备注：仅坐席可见")


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
  suggestion_status: Optional[str] = None
  meta: Optional[str] = None
  is_internal: bool = False
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


class CustomerOrderOut(BaseModel):
  """客户关联订单（演示数据）"""
  order_id: str
  product: str
  status: str
  amount: Optional[float] = None
  express: Optional[str] = None
  tracking_no: Optional[str] = None
  days_since_purchase: Optional[int] = None


class CustomerProfileOut(BaseModel):
  """坐席端客户信息卡：一眼看清这人是谁、来过几次、有什么单子"""
  customer_name: str
  channel: str
  status: str
  first_contact_at: datetime
  last_active_at: Optional[datetime] = None
  total_conversations: int = 0
  total_messages: int = 0
  open_tickets: int = 0
  orders: list[CustomerOrderOut] = []
