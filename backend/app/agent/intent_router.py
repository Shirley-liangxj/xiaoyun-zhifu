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
