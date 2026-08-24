"""评测 Schema"""
from typing import Optional

from pydantic import BaseModel


class EvalQuestionResult(BaseModel):
  """单题评测结果"""
  id: Optional[int] = None
  question: str
  category: str
  difficulty: Optional[str] = None
  expected_behavior: Optional[str] = None
  actual_behavior: Optional[str] = None
  behavior_correct: Optional[bool] = None
  retrieved: bool
  confidence: float
  top_score: float
  top_source: Optional[str] = None
  keyword_hits: list[str] = []
  keyword_hit_rate: Optional[float] = None
  answer_quality_ok: Optional[bool] = None
  error: Optional[str] = None


class ConfusionMatrix(BaseModel):
  """阈值混淆矩阵（confidence_threshold 下行为预测）"""
  false_transfer_count: int
  missed_transfer_count: int
  false_transfer_rate: float
  missed_transfer_rate: float
  correct_count: int


class CategoryEvalStat(BaseModel):
  """分层评测统计"""
  category: str
  total: int
  behavior_accuracy: float
  answer_accuracy: Optional[float] = None
  transfer_accuracy: Optional[float] = None
  false_transfer: int = 0
  missed_transfer: int = 0


class EvalReport(BaseModel):
  """评测报告"""
  total: int
  retrieval_hit_rate: float
  avg_confidence: float
  high_confidence_rate: float
  answer_accuracy_rate: float = 0
  transfer_judgment_accuracy: float = 0
  transfer_accuracy_rate: float = 0
  confusion_matrix: ConfusionMatrix
  category_stats: list[CategoryEvalStat] = []
  confidence_threshold: float = 0.6
  results: list[EvalQuestionResult]
  message: Optional[str] = None
