"""高危前置拦截（纯正则）+ 意图标签常量

改造说明：
- 旧的 classify_intent（LLM 四分类）已删除，由模型 function calling 自主选工具取代。
- 保留 INTENT_LABELS 供前端 plan 卡展示。
- detect_high_risk 只拦「根本不该进业务链」的投诉/法律/曝光类；
  「穿过/粉底/污损」等业务风险留给 calc_refund 工具级判断，
  避免前置正则把「退款试算 + HITL」演示路径吃光。
"""
from __future__ import annotations

import re

INTENT_LABELS = {
  "consult": "咨询类",
  "query": "查询类",
  "action": "操作类",
  "transfer": "转人工",
  "direct_answer": "直接回答",
}

# 根本不该进业务链：投诉/辱骂/法律/曝光。不含 穿过/粉底（那些走 calc_refund）
_HIGH_RISK_RE = re.compile(
  r"投诉|差评|辱骂|律师|起诉|卫生|曝光|报警|工商|消协|315"
)


def detect_high_risk(message: str) -> bool:
  """进 LLM 之前的高危正则拦截。命中则全程 0 次 LLM，直接转人工。"""
  text = (message or "").strip()
  if not text:
    return False
  return bool(_HIGH_RISK_RE.search(text))


def detect_unsupported_capability(message: str) -> str | None:
  """识别当前演示环境无法可靠回答的实时数据或缺失规则。

  返回转人工原因；未命中时返回 None。这里刻意不使用置信度：
  即使检索到相似资料，也不能拿尺码表猜库存、拿物流规则猜订单时效。
  """
  text = re.sub(r"\s+", "", message or "")
  if not text:
    return None

  if "赠品" in text and re.search(r"退回|退还|寄回|换货|退货", text):
    return "知识库缺少赠品退回规则，需要人工确认"

  if re.search(r"库存|有货|现货", text):
    return "演示环境未接入实时库存，需要人工查询"
  if "缺货" in text and re.search(r"补货|到货|补发|什么时候|多久", text):
    return "演示环境未接入补货计划，需要人工查询"

  has_order_number = bool(re.search(r"订单号[^\d]{0,4}\d{4,}", text))
  asks_exact_eta = bool(re.search(r"今天能(送|收)到|什么时候(能)?(送|收|到)|几点(送|到)|预计.*送达", text))
  if has_order_number and asks_exact_eta:
    return "演示环境无法核验该真实订单的实时送达时间，需要人工查询"

  return None
