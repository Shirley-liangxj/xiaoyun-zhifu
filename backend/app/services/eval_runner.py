"""评测运行服务 - 基于评测集验证 RAG 效果"""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.services.ai_suggestion import _calc_confidence
from app.services.rag import search_knowledge

# 评测集路径
EVAL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "eval"
QUESTIONS_FILE = EVAL_DIR / "questions.json"


def load_questions() -> list[dict]:
  """加载评测问题集"""
  if not QUESTIONS_FILE.exists():
    return []
  with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)
  return data.get("questions", [])


def run_evaluation(company_id: int, top_k: int = 3) -> dict:
  """
  对评测集逐题执行 RAG 检索，统计指标。
  返回：检索命中率、平均置信度、逐题详情。
  """
  questions = load_questions()
  if not questions:
    return {
      "total": 0,
      "retrieval_hit_rate": 0,
      "avg_confidence": 0,
      "high_confidence_rate": 0,
      "results": [],
      "message": "评测集为空，请检查 eval/questions.json",
    }

  results = []
  hit_count = 0
  high_conf_count = 0
  total_confidence = 0.0

  for q in questions:
    question = q["question"]
    category = q.get("category", "")
    keywords = q.get("expected_keywords", [])

    try:
      sources = search_knowledge(company_id, question, top_k=top_k)
    except Exception as e:
      sources = []
      error = str(e)
    else:
      error = None

    confidence = _calc_confidence(sources)
    retrieved = len(sources) > 0
    if retrieved:
      hit_count += 1
    if confidence >= 0.7:
      high_conf_count += 1
    total_confidence += confidence

    # 关键词命中率：检索文本中是否包含期望关键词
    all_text = " ".join(s["text"] for s in sources)
    keyword_hits = [kw for kw in keywords if kw in all_text] if keywords else []

    results.append({
      "id": q.get("id"),
      "question": question,
      "category": category,
      "retrieved": retrieved,
      "confidence": confidence,
      "top_score": sources[0]["score"] if sources else 0,
      "top_source": sources[0]["title"] if sources else None,
      "keyword_hits": keyword_hits,
      "keyword_hit_rate": len(keyword_hits) / len(keywords) if keywords else None,
      "error": error,
    })

  total = len(questions)
  return {
    "total": total,
    "retrieval_hit_rate": round(hit_count / total * 100, 1),
    "avg_confidence": round(total_confidence / total, 2),
    "high_confidence_rate": round(high_conf_count / total * 100, 1),
    "results": results,
  }
