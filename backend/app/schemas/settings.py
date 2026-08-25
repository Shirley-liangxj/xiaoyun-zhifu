"""设置 Schema"""
from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
  """公司设置输出"""
  welcome_message: str
  confidence_threshold: float
  auto_suggest: bool
  reject_message: str

  class Config:
    from_attributes = True


class SettingsUpdate(BaseModel):
  """更新设置"""
  welcome_message: str | None = None
  confidence_threshold: float | None = Field(None, ge=0.1, le=1.0)
  auto_suggest: bool | None = None
  reject_message: str | None = None


class CompanyInfoUpdate(BaseModel):
  """更新企业信息"""
  company_name: str = Field(..., min_length=2, max_length=100)


class SystemStatusOut(BaseModel):
  """系统状态"""
  api_key_configured: bool
  api_key_masked: str
  llm_model: str
  embedding_model: str
  knowledge_docs_total: int
  knowledge_docs_indexed: int
  index_ready: bool
  company_name: str
  company_id: int = 1
