"""快捷话术 Schema"""
from datetime import datetime

from pydantic import BaseModel, Field


class QuickReplyCreate(BaseModel):
  category: str = Field(..., max_length=30)
  title: str = Field(..., min_length=1, max_length=100)
  content: str = Field(..., min_length=1)


class QuickReplyUpdate(BaseModel):
  category: str | None = Field(None, max_length=30)
  title: str | None = Field(None, max_length=100)
  content: str | None = Field(None, min_length=1)


class QuickReplyOut(BaseModel):
  id: int
  category: str
  title: str
  content: str
  use_count: int
  created_at: datetime

  class Config:
    from_attributes = True
