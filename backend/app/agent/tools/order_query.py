"""订单查询工具 — 本地 mock，面试如实声明为演示数据"""
from __future__ import annotations

import json
import re
from pathlib import Path

ORDERS_PATH = Path(__file__).resolve().parents[2] / "data" / "orders_demo.json"


def _load_orders() -> list[dict]:
  if not ORDERS_PATH.exists():
    return []
  with open(ORDERS_PATH, encoding="utf-8") as f:
    data = json.load(f)
  return data if isinstance(data, list) else data.get("orders", [])


def extract_order_id(message: str) -> str | None:
  m = re.search(r"(DEMO-\d{3,}|SF\d+|ZT\d+|YT\d+)", message, re.I)
  return m.group(1).upper() if m else None


def query_order(message: str, order_id: str | None = None) -> dict:
  """查演示订单。返回统一工具结构。"""
  orders = _load_orders()
  oid = (order_id or extract_order_id(message) or "").upper()
  found = None
  if oid:
    for o in orders:
      if o.get("order_id", "").upper() == oid or o.get("tracking_no", "").upper() == oid:
        found = o
        break
  if not found and orders:
    # 未点名单号时返回默认演示单，并标明是演示
    found = orders[0]

  if not found:
    return {
      "ok": False,
      "source": "demo_mock",
      "needs_human": False,
      "result": {"message": "未找到演示订单，请提供 DEMO-1001 等演示单号"},
      "summary": "未找到演示订单",
    }

  summary = (
    f"【演示数据】订单 {found['order_id']}｜{found['product']}｜"
    f"状态：{found['status']}｜{found.get('express', '')} {found.get('tracking_no', '')}｜"
    f"{found.get('logistics', '')}"
  )
  return {
    "ok": True,
    "source": "demo_mock",
    "needs_human": False,
    "result": found,
    "summary": summary,
  }
