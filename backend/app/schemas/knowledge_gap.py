"""知识缺口 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeGapOut(BaseModel):
  """知识缺口输出"""
  id: int
  question: str
  hit_count: int
  status: str
  suggested_answer: Optional[str] = None
  last_confidence: Optional[float] = None
  created_at: datetime
  last_seen_at: datetime

  class Config:
    from_attributes = True


class KnowledgeGapResolve(BaseModel):
  """标记知识缺口已解决"""
  suggested_answer: str = Field(..., min_length=1)
