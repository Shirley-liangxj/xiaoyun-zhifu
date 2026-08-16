"""公开接口 Schema"""
from pydantic import BaseModel, Field


class PublicChatRequest(BaseModel):
  """买家端对话请求"""
  message: str = Field(..., min_length=1, max_length=500)
  conversation_id: int | None = None
  customer_name: str = Field(default="访客", max_length=50)


class SourceItem(BaseModel):
  doc_id: int
  title: str
  category: str
  text: str
  score: float


class PublicChatResponse(BaseModel):
  """买家端对话响应"""
  conversation_id: int
  message_id: int
  answer: str
  confidence: float
  need_human: bool
  sources: list[SourceItem]
