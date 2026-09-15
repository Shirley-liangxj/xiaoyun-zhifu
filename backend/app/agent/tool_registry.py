"""工具注册表 — 统一 name/description/run"""
from __future__ import annotations

from typing import Any, Callable

from app.agent.tools.order_query import query_order
from app.agent.tools.refund_calc import calc_refund


ToolFn = Callable[..., dict]


class ToolSpec:
  def __init__(self, name: str, description: str, run: ToolFn):
    self.name = name
    self.description = description
    self.run = run


REGISTRY: dict[str, ToolSpec] = {
  "query_order": ToolSpec(
    name="query_order",
    description="查询演示订单/物流状态（mock）",
    run=lambda message, **kwargs: query_order(message, kwargs.get("order_id")),
  ),
  "calc_refund": ToolSpec(
    name="calc_refund",
    description="按演示规则试算退款，需人工确认后才执行",
    run=lambda message, **kwargs: calc_refund(
      message,
      amount=kwargs.get("amount"),
      days_since_purchase=kwargs.get("days_since_purchase"),
      order_id=kwargs.get("order_id"),
    ),
  ),
}


def list_tools() -> list[dict[str, str]]:
  return [{"name": t.name, "description": t.description} for t in REGISTRY.values()]


def run_tool(name: str, message: str, **kwargs: Any) -> dict:
  spec = REGISTRY.get(name)
  if not spec:
    return {
      "ok": False,
      "source": "system",
      "needs_human": False,
      "result": {"error": f"unknown tool: {name}"},
      "summary": f"未知工具 {name}",
    }
  out = spec.run(message, **kwargs)
  out.setdefault("tool", name)
  return out
