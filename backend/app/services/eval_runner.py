"""评测运行服务 - 基于评测集验证 RAG 效果与转人工判断"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from app.services.ai_suggestion import _calc_confidence
from app.services.rag import search_knowledge

EVAL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "eval"
QUESTIONS_FILE = EVAL_DIR / "questions.json"


def load_questions() -> list[dict]:
  """加载评测问题集"""
  if not QUESTIONS_FILE.exists():
    return []
  with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)
  return data.get("questions", [])


def _predict_transfer(confidence: float, sources: list, threshold: float) -> bool:
  """与买家端 public_chat 一致：低置信或无检索结果则转人工"""
  return confidence < threshold or not sources


def _actual_behavior(confidence: float, sources: list, threshold: float) -> str:
  return "transfer_human" if _predict_transfer(confidence, sources, threshold) else "answer"


def _answer_quality_ok(keywords: list[str], keyword_hits: list[str], retrieved: bool) -> bool:
  """回答类题目：检索命中且关键词覆盖达标"""
  if not keywords:
    return retrieved
  if not keyword_hits:
    return False
  return len(keyword_hits) / len(keywords) >= 0.5


def run_evaluation(company_id: int, top_k: int = 3, confidence_threshold: float = 0.6) -> dict:
  """
  对评测集逐题执行 RAG 检索，统计检索指标 + 转人工判断 + 阈值混淆矩阵。
  """
  questions = load_questions()
  if not questions:
    return {
      "total": 0,
      "retrieval_hit_rate": 0,
      "avg_confidence": 0,
      "high_confidence_rate": 0,
      "answer_accuracy_rate": 0,
      "transfer_judgment_accuracy": 0,
      "transfer_accuracy_rate": 0,
      "confusion_matrix": {
        "false_transfer_count": 0,
        "missed_transfer_count": 0,
        "false_transfer_rate": 0,
        "missed_transfer_rate": 0,
        "correct_count": 0,
      },
      "category_stats": [],
      "confidence_threshold": confidence_threshold,
      "results": [],
      "message": "评测集为空，请检查 eval/questions.json",
    }

  results = []
  hit_count = 0
  high_conf_count = 0
  total_confidence = 0.0

  behavior_correct = 0
  answer_expected = 0
  answer_quality_ok = 0
  transfer_expected = 0
  transfer_correct = 0
  false_transfer = 0
  missed_transfer = 0

  category_agg: dict[str, dict] = defaultdict(lambda: {
    "total": 0,
    "behavior_correct": 0,
    "answer_expected": 0,
    "answer_quality_ok": 0,
    "transfer_expected": 0,
    "transfer_correct": 0,
    "false_transfer": 0,
    "missed_transfer": 0,
  })

  for q in questions:
    question = q["question"]
    category = q.get("category", "")
    keywords = q.get("expected_keywords", [])
    expected_behavior = q.get("expected_behavior", "answer")

    try:
      sources = search_knowledge(company_id, question, top_k=top_k)
    except Exception as e:
      sources = []
      error = str(e)
    else:
      error = None

    confidence = _calc_confidence(sources)
    retrieved = len(sources) > 0
    actual = _actual_behavior(confidence, sources, confidence_threshold)
    is_behavior_correct = actual == expected_behavior

    if retrieved:
      hit_count += 1
    if confidence >= confidence_threshold:
      high_conf_count += 1
    total_confidence += confidence

    all_text = " ".join(s["text"] for s in sources)
    keyword_hits = [kw for kw in keywords if kw in all_text] if keywords else []
    keyword_hit_rate = len(keyword_hits) / len(keywords) if keywords else None
    answer_ok = _answer_quality_ok(keywords, keyword_hits, retrieved)

    if is_behavior_correct:
      behavior_correct += 1

    if expected_behavior == "answer":
      answer_expected += 1
      if answer_ok:
        answer_quality_ok += 1
      if actual == "transfer_human":
        false_transfer += 1
    elif expected_behavior == "transfer_human":
      transfer_expected += 1
      if actual == "transfer_human":
        transfer_correct += 1
      else:
        missed_transfer += 1

    agg = category_agg[category]
    agg["total"] += 1
    if is_behavior_correct:
      agg["behavior_correct"] += 1
    if expected_behavior == "answer":
      agg["answer_expected"] += 1
      if answer_ok:
        agg["answer_quality_ok"] += 1
      if actual == "transfer_human":
        agg["false_transfer"] += 1
    elif expected_behavior == "transfer_human":
      agg["transfer_expected"] += 1
      if actual == "transfer_human":
        agg["transfer_correct"] += 1
      else:
        agg["missed_transfer"] += 1

    results.append({
      "id": q.get("id"),
      "question": question,
      "category": category,
      "difficulty": q.get("difficulty"),
      "expected_behavior": expected_behavior,
      "actual_behavior": actual,
      "behavior_correct": is_behavior_correct,
      "retrieved": retrieved,
      "confidence": confidence,
      "top_score": sources[0]["score"] if sources else 0,
      "top_source": sources[0]["title"] if sources else None,
      "keyword_hits": keyword_hits,
      "keyword_hit_rate": keyword_hit_rate,
      "answer_quality_ok": answer_ok,
      "error": error,
    })

  total = len(questions)
  category_stats = []
  for cat, agg in sorted(category_agg.items()):
    ae = agg["answer_expected"]
    te = agg["transfer_expected"]
    category_stats.append({
      "category": cat,
      "total": agg["total"],
      "behavior_accuracy": round(agg["behavior_correct"] / agg["total"] * 100, 1) if agg["total"] else 0,
      "answer_accuracy": round(agg["answer_quality_ok"] / ae * 100, 1) if ae else None,
      "transfer_accuracy": round(agg["transfer_correct"] / te * 100, 1) if te else None,
      "false_transfer": agg["false_transfer"],
      "missed_transfer": agg["missed_transfer"],
    })

  return {
    "total": total,
    "retrieval_hit_rate": round(hit_count / total * 100, 1),
    "avg_confidence": round(total_confidence / total, 2),
    "high_confidence_rate": round(high_conf_count / total * 100, 1),
    "answer_accuracy_rate": round(answer_quality_ok / answer_expected * 100, 1) if answer_expected else 0,
    "transfer_judgment_accuracy": round(behavior_correct / total * 100, 1),
    "transfer_accuracy_rate": round(transfer_correct / transfer_expected * 100, 1) if transfer_expected else 0,
    "confusion_matrix": {
      "false_transfer_count": false_transfer,
      "missed_transfer_count": missed_transfer,
      "false_transfer_rate": round(false_transfer / answer_expected * 100, 1) if answer_expected else 0,
      "missed_transfer_rate": round(missed_transfer / transfer_expected * 100, 1) if transfer_expected else 0,
      "correct_count": behavior_correct,
    },
    "category_stats": category_stats,
    "confidence_threshold": confidence_threshold,
    "results": results,
  }
