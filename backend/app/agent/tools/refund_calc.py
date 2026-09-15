"""退款试算 — 纯规则，执行必须 HITL，绝不自动打款"""
from __future__ import annotations

import re


def _parse_amount_and_days(message: str) -> tuple[float | None, int | None]:
  amount = None
  days = None
  m_amt = re.search(r"(\d+(?:\.\d+)?)\s*元", message)
  if m_amt:
    amount = float(m_amt.group(1))
  m_day = re.search(r"第?\s*(\d+)\s*天", message)
  if m_day:
    days = int(m_day.group(1))
  return amount, days


def calc_refund(
  message: str,
  amount: float | None = None,
  days_since_purchase: int | None = None,
  order_id: str | None = None,
) -> dict:
  """
  规则（演示）：
  - ≤7 天且未声明已穿着：可全额试算
  - 8–15 天：试算 80%
  - >15 天：建议转人工，试算 0
  返回 needs_human=True，禁止自动执行。
  """
  parsed_amount, parsed_days = _parse_amount_and_days(message)
  amt = amount if amount is not None else (parsed_amount if parsed_amount is not None else 199.0)
  days = days_since_purchase if days_since_purchase is not None else (parsed_days if parsed_days is not None else 5)

  worn = bool(re.search(r"穿过|穿了|沾了|污损", message))
  if worn:
    refund = 0.0
    reason = "疑似已穿着/污损，演示规则下不自动退款，需人工核实"
    eligible = False
  elif days <= 7:
    refund = round(amt, 2)
    reason = "签收后 7 天内（演示规则）可全额退款试算"
    eligible = True
  elif days <= 15:
    refund = round(amt * 0.8, 2)
    reason = "第 8–15 天（演示规则）按 80% 试算"
    eligible = True
  else:
    refund = 0.0
    reason = "超过 15 天（演示规则）需人工审核，试算为 0"
    eligible = False

  summary = (
    f"【演示试算】订单金额 ¥{amt:.2f}，购后第 {days} 天 → 建议退款 ¥{refund:.2f}。"
    f"{reason}。退款不会自动执行，需人工确认。"
  )
  return {
    "ok": True,
    "source": "demo_rule",
    "needs_human": True,
    "result": {
      "order_id": order_id or "DEMO-PENDING",
      "order_amount": amt,
      "days_since_purchase": days,
      "refund_amount": refund,
      "eligible": eligible,
      "reason": reason,
      "auto_execute": False,
      "demo": True,
    },
    "summary": summary,
  }
