"""知识缺口服务 - 记录与处理未命中问题"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import KnowledgeGap


def record_knowledge_gap(
  db: Session,
  company_id: int,
  question: str,
  confidence: float,
  threshold: float = 0.4,
) -> KnowledgeGap | None:
  """
  当置信度低于阈值或无检索结果时，记录知识缺口。
  同一问题累加 hit_count。
  """
  if confidence >= threshold:
    return None

  existing = db.query(KnowledgeGap).filter(
    KnowledgeGap.company_id == company_id,
    KnowledgeGap.question == question,
    KnowledgeGap.status == "pending",
  ).first()

  if existing:
    existing.hit_count += 1
    existing.last_seen_at = datetime.utcnow()
    existing.last_confidence = confidence
    db.commit()
    db.refresh(existing)
    return existing

  gap = KnowledgeGap(
    company_id=company_id,
    question=question,
    last_confidence=confidence,
  )
  db.add(gap)
  db.commit()
  db.refresh(gap)
  return gap
