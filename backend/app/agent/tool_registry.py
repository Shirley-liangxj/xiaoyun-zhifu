"""工具注册表 — 统一 name/description/parameters/run

parameters 是给模型看的「参数说明书」（JSON Schema）。模型靠它才知道：
有哪些工具可用、每个工具干什么、调用时需要提供什么参数。
这是 function calling 的必要条件 —— 只给 name + description，模型不知道怎么传参。

向后兼容：parameters 为可选参数，不传时自动补一个合法的空 schema，
原有 run_tool(name, message, **kwargs) 的调用方式完全不变。
"""
from __future__ import annotations

from typing import Any, Callable

from app.agent.tools.human_transfer import transfer_to_human
from app.agent.tools.knowledge_search import search_policy
from app.agent.tools.order_query import query_order
from app.agent.tools.refund_calc import calc_refund


ToolFn = Callable[..., dict]

# 空参数 schema：保证任何工具都能拼出合法的 tools 字段
_EMPTY_PARAMS: dict = {"type": "object", "properties": {}, "required": []}


class ToolSpec:
  def __init__(
    self,
    name: str,
    description: str,
    run: ToolFn,
    parameters: dict | None = None,
  ):
    self.name = name
    self.description = description
    self.run = run
    self.parameters = parameters or dict(_EMPTY_PARAMS)

  def to_openai_schema(self) -> dict:
    """转成 GLM / OpenAI 兼容协议的 tools 条目格式。"""
    return {
      "type": "function",
      "function": {
        "name": self.name,
        "description": self.description,
        "parameters": self.parameters,
      },
    }


REGISTRY: dict[str, ToolSpec] = {
  "search_policy": ToolSpec(
    name="search_policy",
    description=(
      "检索知识库中的售后政策、规则与流程（如七天无理由、退换货条件、发货时效、"
      "默认发什么快递/用哪家快递公司、发货方式）。"
      "当用户询问「怎么退」「能不能退」「规则是什么」「发什么快递」这类需要依据资料回答的问题时使用。"
    ),
    parameters={
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "用于检索的查询文本，建议直接用用户原话或改写后的检索词",
        },
      },
      "required": ["query"],
    },
    run=lambda message, **kwargs: search_policy(
      message,
      query=kwargs.get("query"),
      company_id=kwargs.get("company_id"),
      top_k=kwargs.get("top_k", 3),
    ),
  ),
  "query_order": ToolSpec(
    name="query_order",
    description=(
      "查询演示订单的物流与状态（mock 数据，非真实订单系统）。"
      "当用户询问订单进度、快递到哪了、物流状态、什么时候发货时使用。"
      "注意：「发什么快递 / 用什么快递公司」属于政策咨询，应改用 search_policy，不要用本工具。"
    ),
    parameters={
      "type": "object",
      "properties": {
        "order_id": {
          "type": "string",
          "description": (
            "订单号或快递单号，例如 DEMO-1001 / SF1234567890。"
            "如果用户没有提供单号，不要编造，应向用户追问。"
          ),
        },
      },
      "required": [],
    },
    run=lambda message, **kwargs: query_order(
      message,
      order_id=kwargs.get("order_id"),
      fallback_to_first=kwargs.get("fallback_to_first", True),
    ),
  ),
  "calc_refund": ToolSpec(
    name="calc_refund",
    description=(
      "按演示规则试算退款金额。仅做试算，不会执行打款 —— 任何退款都必须人工确认。"
      "当用户提出退款/退货金额诉求时使用；若已知订单金额与购后天数请一并传入。"
    ),
    parameters={
      "type": "object",
      "properties": {
        "order_id": {
          "type": "string",
          "description": "订单号，通常来自 query_order 的返回结果",
        },
        "amount": {
          "type": "number",
          "description": "订单金额（元）。已知则传入；未知可省略，工具会尝试从用户原话中解析",
        },
        "days_since_purchase": {
          "type": "integer",
          "description": "签收/购买后的天数。已知则传入；未知可省略",
        },
      },
      "required": [],
    },
    run=lambda message, **kwargs: calc_refund(
      message,
      amount=kwargs.get("amount"),
      days_since_purchase=kwargs.get("days_since_purchase"),
      order_id=kwargs.get("order_id"),
    ),
  ),
  "transfer_to_human": ToolSpec(
    name="transfer_to_human",
    description=(
      "把本次会话转交人工客服。以下两种情况都必须调用本工具，不得只用文字回答代替："
      "① 用户投诉、情绪激烈、涉及纠纷；"
      "② 问题与服饰售后无关（写代码/编程、天气、股票基金、时事、翻译、游戏、"
      "旅游美食推荐、其他平台业务等）。"
      "调用后不会执行任何自动动作，只标记需要人工介入。"
    ),
    parameters={
      "type": "object",
      "properties": {
        "reason": {
          "type": "string",
          "description": "转人工的原因，例如：用户投诉 / 涉及已穿着退款的纠纷 / 超出售后范围",
        },
      },
      "required": ["reason"],
    },
    run=lambda message, **kwargs: transfer_to_human(message, reason=kwargs.get("reason")),
  ),
}


def list_tools() -> list[dict[str, str]]:
  """工具名 + 描述（轻量清单，供轨迹记录/调试展示用）"""
  return [{"name": t.name, "description": t.description} for t in REGISTRY.values()]


def list_tool_schemas() -> list[dict]:
  """完整 tools 字段，直接喂给 LLMService.complete(tools=...)"""
  return [t.to_openai_schema() for t in REGISTRY.values()]


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
