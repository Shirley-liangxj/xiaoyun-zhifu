"""公开接口 Schema"""
from pydantic import BaseModel, Field


class PublicChatRequest(BaseModel):
  """买家端对话请求"""
  message: str = Field(..., min_length=1, max_length=500)
  conversation_id: int | None = None
  customer_name: str = Field(default="访客", max_length=50)


class PublicTransferRequest(BaseModel):
  conversation_id: int | None = None
  customer_name: str = Field(default="访客", max_length=50)


class SourceItem(BaseModel):
  doc_id: int = 0
  title: str
  category: str = ""
  text: str = ""
  score: float = 0.0


class PublicChatResponse(BaseModel):
  """买家端对话响应"""
  conversation_id: int
  message_id: int
  answer: str
  confidence: float
  need_human: bool
  human_mode: bool = False
  sources: list[SourceItem]


class PublicMessageOut(BaseModel):
  id: int
  role: str
  content: str
  confidence: float | None = None
  sources: list = []
  created_at: str | None = None


class PublicConversationOut(BaseModel):
  conversation_id: int
  status: str
  human_mode: bool
  messages: list[PublicMessageOut]


class PublicConfigOut(BaseModel):
  welcome_message: str
  company_name: str = "云裳服饰"
  confidence_threshold: float = 0.6
