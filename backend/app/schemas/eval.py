"""评测 Schema"""
from typing import Optional

from pydantic import BaseModel


class EvalQuestionResult(BaseModel):
  """单题评测结果"""
  id: Optional[int] = None
  question: str
  category: str
  retrieved: bool
  confidence: float
  top_score: float
  top_source: Optional[str] = None
  keyword_hits: list[str] = []
  keyword_hit_rate: Optional[float] = None
  error: Optional[str] = None


class EvalReport(BaseModel):
  """评测报告"""
  total: int
  retrieval_hit_rate: float
  avg_confidence: float
  high_confidence_rate: float
  confidence_threshold: float = 0.6
  results: list[EvalQuestionResult]
  message: Optional[str] = None
