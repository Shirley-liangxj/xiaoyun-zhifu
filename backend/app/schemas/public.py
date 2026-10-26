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
  """（内部）执行计划步骤 — 仅坐席端使用，不在买家端 schema 中出现"""
  id: str
  title: str
  status: str = "done"
  detail: str = ""
  demo: bool = False


class PendingConfirmationOut(BaseModel):
  """（内部）待确认动作 — 仅坐席端使用；买家端只下发 BuyerActionOut"""
  id: str
  action: str
  title: str
  detail: str = ""
  payload: dict = {}
  demo: bool = True


class OrderCardOut(BaseModel):
  """订单卡片（买家端结构化渲染）— 只含买家看得懂的业务字段"""
  type: str = "order"
  order_id: str
  product: str | None = None
  status: str | None = None
  express: str | None = None
  tracking_no: str | None = None
  logistics: str | None = None
  amount: float | None = None


class BuyerActionOut(BaseModel):
  """买家端待确认动作 — 只给按钮，不给内部动作类型/payload"""
  id: str
  label: str = "确认提交"


class PublicChatResponse(BaseModel):
  """买家端对话响应（买家视图白名单）

  注意：执行计划、工具调用、检索来源、置信度、内部备注等均不在此模型中，
  即使 agent 侧返回了也会被丢弃 —— 买家端接口从设计上就拿不到内部信息。
  """
  conversation_id: int
  message_id: int
  answer: str
  need_human: bool
  human_mode: bool = False
  card: OrderCardOut | None = None
  action: BuyerActionOut | None = None


class PublicMessageOut(BaseModel):
  """买家端单条消息（买家视图白名单）"""
  id: int
  role: str
  content: str
  created_at: str | None = None
  card: OrderCardOut | None = None
  action: BuyerActionOut | None = None


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
