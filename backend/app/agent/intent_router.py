"""意图路由：复用 GLM zero-shot，失败时关键词兜底"""
from __future__ import annotations

import json
import logging
import re

from app.services.errors import ExternalServiceError
from app.services.llm import llm_service

logger = logging.getLogger(__name__)

INTENTS = ("consult", "query", "action", "transfer")

INTENT_LABELS = {
  "consult": "咨询类",
  "query": "查询类",
  "action": "操作类",
  "transfer": "转人工",
}

CLASSIFY_PROMPT = """你是服饰电商售后意图分类器。只输出 JSON，不要其他文字。
意图只能是以下之一：
- consult：问政策/规则/怎么退换货（咨询说明，不立刻办事）
- query：查物流/订单状态/到哪了
- action：要求退款/退货/换货办理、提交申请
- transfer：投诉、情绪激动、已穿着污损、卫生/法律等高风险

用户消息：{message}

输出格式：{{"intent":"consult|query|action|transfer","confidence":0.0到1.0}}"""


def _keyword_intent(message: str) -> tuple[str, float]:
  text = message.strip()
  if re.search(r"投诉|差评|律师|卫生|粉底|穿过|穿了|开线|线头.*(太差|投诉)|质量太差", text):
    return "transfer", 0.85
  if re.search(r"帮我退|给我退|要退款|申请退货|提交退|办理退|我要退|把订单退", text):
    return "action", 0.8
  # 政策咨询优先：发什么快递 / 怎么退，避免被「快递」误判成查物流
  if re.search(r"发什么快递|用什么快递|什么快递|怎么退|如何退|退货政策|七天无理由", text):
    return "consult", 0.85
  # 查询：物流追踪 / 催派
  if re.search(r"到哪|单号|查(一下)?订单|物流(呢|怎么样|不动)|几天没动静|还没到|快递.*(没|到哪|动静)", text):
    return "query", 0.8
  if re.search(r"物流|订单状态|包裹", text) and not re.search(r"发什么|用什么快递|什么快递", text):
    return "query", 0.75
  return "consult", 0.55


def classify_intent(message: str) -> dict:
  """返回 {intent, confidence, label, source}"""
  fallback_intent, fallback_conf = _keyword_intent(message)
  try:
    raw = llm_service.chat(
      [
        {"role": "system", "content": "只输出合法 JSON。"},
        {"role": "user", "content": CLASSIFY_PROMPT.format(message=message)},
      ],
      temperature=0.1,
    )
    # 提取 JSON 块
    match = re.search(r"\{[\s\S]*\}", raw)
    data = json.loads(match.group(0) if match else raw)
    intent = str(data.get("intent", "")).strip().lower()
    conf = float(data.get("confidence", 0.6))
    if intent not in INTENTS:
      intent, conf = fallback_intent, fallback_conf
      source = "keyword_fallback"
    else:
      # 高危关键词优先于模型误判
      if fallback_intent == "transfer" and intent != "transfer":
        intent, conf = "transfer", max(conf, fallback_conf)
        source = "keyword_override"
      elif fallback_intent == "consult" and intent == "query" and re.search(
        r"发什么快递|用什么快递|什么快递|怎么退|如何退|七天无理由", message
      ):
        intent, conf = "consult", max(conf, fallback_conf)
        source = "keyword_override"
      else:
        source = "llm"
    return {
      "intent": intent,
      "confidence": round(min(max(conf, 0.0), 1.0), 3),
      "label": INTENT_LABELS[intent],
      "source": source,
    }
  except (ValueError, ExternalServiceError, json.JSONDecodeError, TypeError) as e:
    logger.warning("intent classify fallback: %s", e)
    return {
      "intent": fallback_intent,
      "confidence": fallback_conf,
      "label": INTENT_LABELS[fallback_intent],
      "source": "keyword_fallback",
    }
