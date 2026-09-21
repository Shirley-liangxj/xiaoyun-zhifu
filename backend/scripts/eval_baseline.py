"""有/无 RAG 消融对照：准确率 + token + 延迟。

从 backend 目录运行：
  python scripts/eval_baseline.py --limit 3 --arms baseline
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.database import SessionLocal
from app.models import CompanySettings
from app.services.ai_suggestion import _build_context, _calc_confidence
from app.services.errors import ExternalServiceError
from app.services.llm import llm_service
from app.services.public_chat import BUYER_SYSTEM_PROMPT
from app.services.rag import search_knowledge

# 与 BUYER_SYSTEM_PROMPT 同文，仅改第 1 条。
# 取舍：若沿用「只依据提供的政策资料回答，禁止编造」，无资料时模型会被 prompt 逼成拒答，
# 人为压低裸模型基线，对照不公平。基线改为「依据常识回答」，才测的是「没有检索」本身。
BASELINE_SYSTEM_PROMPT = """你是「云裳服饰」店铺的售后 AI 客服「小云」，负责回答买家关于退换货、运费、物流、尺码、质量问题的咨询。

要求：
1. 依据你已知的服饰电商售后常识回答
2. 语气亲切口语化，直接给结论
3. 涉及例外条款（定制/预售/贴身衣物）必须说明
4. 控制在 150 字以内
5. 资料不足时明确说明并建议转人工"""

DEFAULT_REJECT = "抱歉，这个问题我需要为您转接人工客服，请稍候。"
QUESTIONS_PATH = os.path.abspath(
  os.path.join(os.path.dirname(__file__), "..", "..", "eval", "questions.json")
)
RESULTS_PATH = os.path.abspath(
  os.path.join(os.path.dirname(__file__), "..", "..", "eval", "baseline_results.json")
)


def _percentile_nearest_rank(values: list[float], pct: float) -> float | None:
  """最近秩法：rank = ceil(pct/100 * N)，取排序后第 rank 个（1-based）。不用 numpy。"""
  if not values:
    return None
  ordered = sorted(values)
  rank = math.ceil(pct / 100.0 * len(ordered))
  rank = max(1, min(rank, len(ordered)))
  return ordered[rank - 1]


def _load_questions(limit: int | None) -> list[dict]:
  with open(QUESTIONS_PATH, encoding="utf-8") as f:
    data = json.load(f)
  questions = data.get("questions", [])
  if limit is not None:
    questions = questions[:limit]
  return questions


def _load_settings(company_id: int) -> tuple[float, str]:
  db = SessionLocal()
  try:
    row = (
      db.query(CompanySettings)
      .filter(CompanySettings.company_id == company_id)
      .first()
    )
    if not row:
      return 0.6, DEFAULT_REJECT
    threshold = row.confidence_threshold if row.confidence_threshold is not None else 0.6
    reject = (row.reject_message or "").strip() or DEFAULT_REJECT
    return float(threshold), reject
  finally:
    db.close()


def _score_answer(text: str, keywords: list[str]) -> tuple[list[str], float | None, bool]:
  """与 eval_runner._answer_quality_ok 同一口径：关键词命中率 >= 0.5 判对。
  判定对象是模型生成文本（或拒答话术），不用检索片段。
  """
  hits = [kw for kw in keywords if kw in (text or "")]
  if not keywords:
    return hits, None, False
  rate = len(hits) / len(keywords)
  return hits, rate, rate >= 0.5


def _arm_baseline(question: str) -> dict:
  result = llm_service.complete(
    [
      {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
      {"role": "user", "content": f"## 客户问题\n{question}\n\n请回答："},
    ],
    temperature=0,
  )
  text = (result.content or "").strip()
  # A 臂没有检索置信度；need_human 仅作文本信号记录，判转人工时另看「人工/转接」
  need_human = ("人工" in text) or ("转接" in text)
  usage = result.usage or {}
  return {
    "answer": text,
    "need_human": need_human,
    "prompt_tokens": usage.get("prompt_tokens") or 0,
    "completion_tokens": usage.get("completion_tokens") or 0,
    "total_tokens": usage.get("total_tokens") or 0,
    "latency_ms": result.latency_ms or 0,
    "llm_called": True,
    "error": None,
  }


def _arm_rag(company_id: int, question: str, threshold: float, reject_message: str) -> dict:
  sources = search_knowledge(company_id, question, top_k=3)
  confidence = _calc_confidence(sources)
  need_human = (confidence < threshold) or (not sources)
  if need_human:
    return {
      "answer": reject_message,
      "need_human": True,
      "prompt_tokens": 0,
      "completion_tokens": 0,
      "total_tokens": 0,
      "latency_ms": 0,
      "llm_called": False,
      "error": None,
    }
  context = _build_context(sources)
  result = llm_service.complete(
    [
      {"role": "system", "content": BUYER_SYSTEM_PROMPT},
      {
        "role": "user",
        "content": f"## 政策资料\n{context}\n\n## 客户问题\n{question}\n\n请回答：",
      },
    ],
    temperature=0,
  )
  usage = result.usage or {}
  return {
    "answer": (result.content or "").strip(),
    "need_human": False,
    "prompt_tokens": usage.get("prompt_tokens") or 0,
    "completion_tokens": usage.get("completion_tokens") or 0,
    "total_tokens": usage.get("total_tokens") or 0,
    "latency_ms": result.latency_ms or 0,
    "llm_called": True,
    "error": None,
  }


def _judge(expected_behavior: str, arm: str, answer: str, keywords: list[str], need_human: bool) -> tuple[list, float | None, bool]:
  if expected_behavior == "transfer_human":
    if arm == "rag":
      correct = bool(need_human)
    else:
      # A 臂没有 need_human 概念，只能用文本信号
      correct = ("人工" in (answer or "")) or ("转接" in (answer or ""))
    return [], None, correct
  hits, rate, correct = _score_answer(answer, keywords)
  return hits, rate, correct


def _empty_row(arm: str, q: dict, error: str) -> dict:
  return {
    "arm": arm,
    "id": q.get("id"),
    "category": q.get("category"),
    "difficulty": q.get("difficulty"),
    "expected_behavior": q.get("expected_behavior"),
    "question": q.get("question"),
    "answer": "",
    "need_human": False,
    "keyword_hits": [],
    "keyword_hit_rate": None,
    "correct": False,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "latency_ms": 0,
    "error": error,
  }


def _run_one(arm: str, q: dict, company_id: int, threshold: float, reject_message: str) -> dict:
  question = q["question"]
  try:
    if arm == "baseline":
      raw = _arm_baseline(question)
    else:
      raw = _arm_rag(company_id, question, threshold, reject_message)
  except (ExternalServiceError, ValueError, Exception) as e:
    return _empty_row(arm, q, str(e))

  hits, rate, correct = _judge(
    q.get("expected_behavior", "answer"),
    arm,
    raw["answer"],
    q.get("expected_keywords") or [],
    raw["need_human"],
  )
  return {
    "arm": arm,
    "id": q.get("id"),
    "category": q.get("category"),
    "difficulty": q.get("difficulty"),
    "expected_behavior": q.get("expected_behavior"),
    "question": question,
    "answer": raw["answer"],
    "need_human": raw["need_human"],
    "keyword_hits": hits,
    "keyword_hit_rate": rate,
    "correct": correct,
    "prompt_tokens": raw["prompt_tokens"],
    "completion_tokens": raw["completion_tokens"],
    "total_tokens": raw["total_tokens"],
    "latency_ms": raw["latency_ms"],
    "error": raw["error"],
    "_llm_called": raw["llm_called"],
  }


def _arm_summary(rows: list[dict]) -> dict:
  def _subset(behavior: str | None) -> list[dict]:
    if behavior is None:
      return rows
    return [r for r in rows if r.get("expected_behavior") == behavior]

  def _acc(items: list[dict]) -> float | None:
    if not items:
      return None
    return round(sum(1 for r in items if r.get("correct")) / len(items) * 100, 2)

  answer_rows = _subset("answer")
  transfer_rows = _subset("transfer_human")
  called = [r for r in rows if r.get("_llm_called") and not r.get("error")]
  latencies = [r["latency_ms"] for r in called]
  n_called = len(called)

  def _avg(key: str) -> float | None:
    if not n_called:
      return None
    return round(sum(r[key] for r in called) / n_called, 2)

  by_cat: dict[str, list] = defaultdict(list)
  for r in rows:
    by_cat[r.get("category") or "未分类"].append(r)

  categories = {}
  for cat, items in sorted(by_cat.items()):
    ans = [r for r in items if r.get("expected_behavior") == "answer"]
    categories[cat] = {
      "n": len(items),
      "answer_n": len(ans),
      "answer_accuracy": _acc(ans),
      "overall_accuracy": _acc(items),
    }

  avg_total = _avg("total_tokens")
  cost = None
  if avg_total is not None:
    # GLM-4-Air ¥0.5 / 百万 tokens，输入输出同价；折算每 1000 轮
    cost = round(avg_total / 1_000_000 * 0.5 * 1000, 4)

  return {
    "n": len(rows),
    "answer_n": len(answer_rows),
    "transfer_n": len(transfer_rows),
    "answer_accuracy": _acc(answer_rows),
    "transfer_accuracy": _acc(transfer_rows),
    "overall_accuracy": _acc(rows),
    "llm_called_count": n_called,
    "avg_prompt_tokens": _avg("prompt_tokens"),
    "avg_completion_tokens": _avg("completion_tokens"),
    "avg_total_tokens": avg_total,
    "latency_p50_ms": _percentile_nearest_rank(latencies, 50),
    "latency_p95_ms": _percentile_nearest_rank(latencies, 95),
    "total_llm_calls": n_called,
    "failed_count": sum(1 for r in rows if r.get("error")),
    "cost_per_1000_chats_cny": cost,
    "by_category": categories,
  }


def _fmt(v, width: int, digits: int | None = None) -> str:
  if v is None:
    s = "-"
  elif isinstance(v, float) and digits is not None:
    s = f"{v:.{digits}f}"
  else:
    s = str(v)
  return s.rjust(width)


def _print_table(summaries: dict[str, dict], model: str) -> None:
  headers = [
    ("arm", 10),
    ("ans%", 8),
    ("xfer%", 8),
    ("all%", 8),
    ("llm_n", 7),
    ("avg_tok", 9),
    ("p50ms", 8),
    ("p95ms", 8),
    ("fail", 5),
    ("¥/1k", 8),
  ]
  line = " ".join(name.rjust(w) for name, w in headers)
  print("\n" + "=" * len(line))
  print(f"model={model}  （glm-4-flash 当前免费，线上实付为 0；成本按 GLM-4-Air ¥0.5/百万 tokens 折算）")
  print("=" * len(line))
  print(line)
  print("-" * len(line))
  for arm, s in summaries.items():
    cells = [
      _fmt(arm, 10),
      _fmt(s["answer_accuracy"], 8, 2),
      _fmt(s["transfer_accuracy"], 8, 2),
      _fmt(s["overall_accuracy"], 8, 2),
      _fmt(s["llm_called_count"], 7),
      _fmt(s["avg_total_tokens"], 9, 1),
      _fmt(s["latency_p50_ms"], 8, 1),
      _fmt(s["latency_p95_ms"], 8, 1),
      _fmt(s["failed_count"], 5),
      _fmt(s["cost_per_1000_chats_cny"], 8, 4),
    ]
    print(" ".join(cells))
    print(
      f"         answer_n={s['answer_n']} transfer_n={s['transfer_n']} "
      f"token均值分母(llm_called_count)={s['llm_called_count']}"
    )
  print("=" * len(line))

  if "baseline" in summaries and "rag" in summaries:
    b, r = summaries["baseline"], summaries["rag"]

    def _sub(a, c):
      if a is None or c is None:
        return None
      return round(c - a, 2)

    print("差值（RAG - baseline）:")
    print(f"  overall_accuracy  {_sub(b['overall_accuracy'], r['overall_accuracy'])} 百分点")
    print(f"  answer_accuracy   {_sub(b['answer_accuracy'], r['answer_accuracy'])} 百分点")
    print(f"  transfer_accuracy {_sub(b['transfer_accuracy'], r['transfer_accuracy'])} 百分点")
    print(f"  avg_total_tokens  {_sub(b['avg_total_tokens'], r['avg_total_tokens'])}")
    print(f"  latency_p50_ms    {_sub(b['latency_p50_ms'], r['latency_p50_ms'])}")

  print("\n按 category（answer_accuracy / overall_accuracy）:")
  cats = set()
  for s in summaries.values():
    cats.update(s["by_category"].keys())
  for cat in sorted(cats):
    parts = [f"{cat}:"]
    for arm, s in summaries.items():
      c = s["by_category"].get(cat, {})
      parts.append(
        f"{arm} ans={c.get('answer_accuracy')} all={c.get('overall_accuracy')} (n={c.get('n', 0)})"
      )
    print("  " + " | ".join(parts))


def main() -> None:
  parser = argparse.ArgumentParser(description="有/无 RAG 消融对照")
  parser.add_argument("--company-id", type=int, default=1)
  parser.add_argument("--limit", type=int, default=None, help="只跑前 N 题")
  parser.add_argument("--arms", choices=["both", "baseline", "rag"], default="both")
  args = parser.parse_args()

  questions = _load_questions(args.limit)
  threshold, reject_message = _load_settings(args.company_id)
  arms = ["baseline", "rag"] if args.arms == "both" else [args.arms]
  total = len(questions)

  print(
    f"questions={total} company_id={args.company_id} threshold={threshold} "
    f"model={settings.LLM_MODEL} arms={arms}"
  )

  details: list[dict] = []
  for arm in arms:
    for i, q in enumerate(questions, 1):
      row = _run_one(arm, q, args.company_id, threshold, reject_message)
      details.append(row)
      if i % 10 == 0 or i == total:
        status = "fail" if row.get("error") else "ok"
        print(f"[{i}/{total}] {arm} {status}")
      if i < total or arm != arms[-1]:
        time.sleep(0.3)

  public_details = []
  for row in details:
    item = dict(row)
    item.pop("_llm_called", None)
    public_details.append(item)

  summaries = {}
  for arm in arms:
    summaries[arm] = _arm_summary([r for r in details if r["arm"] == arm])

  delta = None
  if "baseline" in summaries and "rag" in summaries:
    b, r = summaries["baseline"], summaries["rag"]

    def _sub(a, c):
      if a is None or c is None:
        return None
      return round(c - a, 2)

    delta = {
      "overall_accuracy_pp": _sub(b["overall_accuracy"], r["overall_accuracy"]),
      "answer_accuracy_pp": _sub(b["answer_accuracy"], r["answer_accuracy"]),
      "transfer_accuracy_pp": _sub(b["transfer_accuracy"], r["transfer_accuracy"]),
      "avg_total_tokens": _sub(b["avg_total_tokens"], r["avg_total_tokens"]),
      "latency_p50_ms": _sub(b["latency_p50_ms"], r["latency_p50_ms"]),
      "latency_p95_ms": _sub(b["latency_p95_ms"], r["latency_p95_ms"]),
    }

  summary = {
    "model": settings.LLM_MODEL,
    "cost_note": "cost_per_1000_chats_cny 按 GLM-4-Air ¥0.5/百万 tokens（输入输出同价）折算；glm-4-flash 当前免费，线上实付为 0",
    "company_id": args.company_id,
    "confidence_threshold": threshold,
    "reject_message": reject_message,
    "question_count": total,
    "arms": summaries,
    "delta_rag_minus_baseline": delta,
  }

  payload = {"summary": summary, "details": public_details}
  os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
  with open(RESULTS_PATH, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

  _print_table(summaries, settings.LLM_MODEL)
  print(f"\n写入 {RESULTS_PATH}")


if __name__ == "__main__":
  main()
