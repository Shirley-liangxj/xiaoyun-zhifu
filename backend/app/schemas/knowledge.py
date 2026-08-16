"""知识库 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeDocCreate(BaseModel):
  """创建知识库文档"""
  title: str = Field(..., min_length=1, max_length=200)
  content: str = Field(..., min_length=1)
  category: str = Field(default="通用", max_length=50)


class KnowledgeDocUpdate(BaseModel):
  """更新知识库文档"""
  title: Optional[str] = Field(None, min_length=1, max_length=200)
  content: Optional[str] = Field(None, min_length=1)
  category: Optional[str] = Field(None, max_length=50)


class KnowledgeDocOut(BaseModel):
  """知识库文档输出"""
  id: int
  title: str
  content: str
  category: str
  is_indexed: bool
  created_at: datetime
  updated_at: datetime

  class Config:
    from_attributes = True


class KnowledgeSearchRequest(BaseModel):
  """知识库检索请求"""
  query: str = Field(..., min_length=1, max_length=500)
  top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
  """单条检索结果"""
  doc_id: int
  title: str
  category: str
  text: str
  score: float


class KnowledgeSearchResponse(BaseModel):
  """检索响应"""
  query: str
  results: list[KnowledgeSearchResult]
