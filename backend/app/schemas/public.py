"""公开接口 Schema"""
from pydantic import BaseModel, Field


class PublicChatRequest(BaseModel):
  """买家端对话请求"""
  message: str = Field(..., min_length=1, max_length=500)
  conversation_id: int | None = None
  customer_name: str = Field(default="访客", max_length=50)
  company_id: int | None = Field(None, description="租户公司 ID")


class PublicTransferRequest(BaseModel):
  conversation_id: int | None = None
  customer_name: str = Field(default="访客", max_length=50)
  company_id: int | None = Field(None, description="租户公司 ID")


class PublicConfirmRequest(BaseModel):
  confirmation_id: str = Field(..., min_length=1)
  conversation_id: int | None = None
  customer_name: str = Field(default="访客", max_length=50)
  company_id: int | None = None


class SourceItem(BaseModel):
  doc_id: int = 0
  title: str
  category: str = ""
  text: str = ""
  score: float = 0.0


class PlanStepOut(BaseModel):
  id: str
  title: str
  status: str = "done"
  detail: str = ""
  demo: bool = False


class PendingConfirmationOut(BaseModel):
  id: str
  action: str
  title: str
  detail: str = ""
  payload: dict = {}
  demo: bool = True


class PublicChatResponse(BaseModel):
  """买家端对话响应"""
  conversation_id: int
  message_id: int
  answer: str
  confidence: float
  need_human: bool
  human_mode: bool = False
  sources: list[SourceItem] = []
  intent: str | None = None
  intent_label: str | None = None
  plan_steps: list[PlanStepOut] = []
  pending_confirmation: PendingConfirmationOut | None = None
  review_status: str | None = None
  terminal_state: str = "answered"


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
  company_name: str = "智能客服"
  company_id: int = 1
  confidence_threshold: float = 0.6
