"""统一 Agent 入口：意图 → 工具/RAG → 轨迹 → HITL"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.agent.intent_router import INTENT_LABELS, classify_intent
from app.agent.tool_registry import run_tool
from app.agent.trajectory import append_trace
from app.models import Conversation, Message
from app.services.ai_suggestion import _build_context, _calc_confidence, generate_suggestion
from app.services.errors import ExternalServiceError
from app.services.knowledge_gap import record_knowledge_gap
from app.services.llm import llm_service
from app.services.public_chat import (
  BUYER_SYSTEM_PROMPT,
  TRANSFER_NOTE,
  _is_human_mode,
  get_or_create_conversation,
)
from app.services.rag import search_knowledge
from app.services.settings import get_or_create_settings

PENDING_PATH = Path(__file__).resolve().parents[2] / "data" / "pending_confirmations.json"


def _load_pending() -> dict:
  if not PENDING_PATH.exists():
    return {}
  try:
    with open(PENDING_PATH, encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return {}


def _save_pending(data: dict) -> None:
  PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
  with open(PENDING_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)


def _base_result(
  conv: Conversation,
  ai_msg: Message | None,
  *,
  answer: str,
  confidence: float,
  need_human: bool,
  sources: list,
  intent: dict,
  plan_steps: list,
  pending_confirmation: dict | None,
  human_mode: bool,
) -> dict:
  return {
    "conversation_id": conv.id,
    "message_id": ai_msg.id if ai_msg else 0,
    "answer": answer,
    "confidence": confidence,
    "need_human": need_human,
    "human_mode": human_mode,
    "sources": sources,
    "intent": intent.get("intent"),
    "intent_label": intent.get("label"),
    "plan_steps": plan_steps,
    "pending_confirmation": pending_confirmation,
  }


def _save_ai_message(
  db: Session,
  conv: Conversation,
  content: str,
  confidence: float,
  sources_data: list,
) -> Message:
  ai_msg = Message(
    conversation_id=conv.id,
    role="ai_suggestion",
    content=content.strip(),
    confidence=confidence,
    sources=json.dumps(sources_data, ensure_ascii=False),
    is_sent=True,
  )
  db.add(ai_msg)
  db.commit()
  db.refresh(ai_msg)
  return ai_msg


def _run_consult(
  db: Session,
  company_id: int,
  conv: Conversation,
  message: str,
  company_settings,
  threshold: float,
) -> tuple[Message, str, float, bool, list, list]:
  try:
    sources = search_knowledge(company_id, message, top_k=3)
  except Exception:
    sources = []

  confidence = _calc_confidence(sources)
  need_human = confidence < threshold or not sources
  record_knowledge_gap(db, company_id, message, confidence, threshold)
  sources_data = [
    {
      "doc_id": s["doc_id"],
      "title": s["title"],
      "category": s["category"],
      "text": s["text"],
      "score": s["score"],
    }
    for s in sources
  ]

  if need_human:
    answer = company_settings.reject_message or TRANSFER_NOTE
    conv.status = "waiting_human"
  else:
    context = _build_context(sources)
    user_prompt = f"""## 政策资料
{context}

## 客户问题
{message}

请回答："""
    try:
      answer = llm_service.chat([
        {"role": "system", "content": BUYER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
      ])
    except (ValueError, ExternalServiceError):
      answer = company_settings.reject_message or TRANSFER_NOTE
      need_human = True
      conv.status = "waiting_human"

  ai_msg = _save_ai_message(db, conv, answer, confidence, sources_data)
  plan = [
    {"id": "intent", "title": "意图识别", "status": "done", "detail": "咨询类 → RAG 知识库", "demo": False},
    {
      "id": "rag",
      "title": "知识检索与回答",
      "status": "needs_confirm" if need_human else "done",
      "detail": "低置信已转人工" if need_human else f"置信度 {confidence:.2f}",
      "demo": False,
    },
  ]
  return ai_msg, ai_msg.content, confidence, need_human, sources_data, plan


def run_agent_turn(
  db: Session,
  company_id: int,
  message: str,
  conversation_id: int | None = None,
  customer_name: str = "访客",
) -> dict:
  company_settings = get_or_create_settings(db, company_id)
  threshold = company_settings.confidence_threshold
  conv = get_or_create_conversation(db, company_id, conversation_id, customer_name)

  db.add(Message(conversation_id=conv.id, role="customer", content=message, is_sent=True))
  db.commit()

  # 已在人工队列：保持旧行为
  if conv.status == "waiting_human":
    try:
      generate_suggestion(db, conv, message)
    except Exception:
      pass
    intent = {"intent": "transfer", "label": INTENT_LABELS["transfer"], "confidence": 1.0, "source": "human_mode"}
    append_trace({
      "conversation_id": conv.id,
      "company_id": company_id,
      "input": message,
      "intent": intent,
      "tools": [],
      "output": "",
      "needs_human": True,
    })
    return _base_result(
      conv, None,
      answer="",
      confidence=0.0,
      need_human=True,
      sources=[],
      intent=intent,
      plan_steps=[],
      pending_confirmation=None,
      human_mode=True,
    )

  intent = classify_intent(message)
  tools_log: list[dict] = []
  plan_steps: list[dict] = [
    {
      "id": "intent",
      "title": "意图识别",
      "status": "done",
      "detail": f"{intent['label']}（{intent.get('source', '')} · {intent['confidence']}）",
      "demo": False,
    }
  ]
  pending = None
  sources_data: list = []
  confidence = intent["confidence"]
  need_human = False
  answer = ""
  ai_msg = None

  if intent["intent"] == "transfer":
    answer = company_settings.reject_message or TRANSFER_NOTE
    conv.status = "waiting_human"
    need_human = True
    confidence = min(confidence, 0.35)
    ai_msg = _save_ai_message(db, conv, answer, confidence, [])
    plan_steps.append({
      "id": "transfer",
      "title": "转人工",
      "status": "needs_confirm",
      "detail": "高风险/投诉类，已进入待人工队列",
      "demo": False,
    })

  elif intent["intent"] == "query":
    tool_out = run_tool("query_order", message)
    tools_log.append({"name": "query_order", "output": tool_out})
    answer = tool_out.get("summary") or "未查到演示订单信息。"
    confidence = 0.9 if tool_out.get("ok") else 0.4
    ai_msg = _save_ai_message(db, conv, answer, confidence, [])
    plan_steps.append({
      "id": "query_order",
      "title": "查询订单（演示）",
      "status": "done" if tool_out.get("ok") else "pending",
      "detail": tool_out.get("summary", ""),
      "demo": True,
    })

  elif intent["intent"] == "action":
    # 先查演示单再试算，形成可解释计划
    order_out = run_tool("query_order", message)
    tools_log.append({"name": "query_order", "output": order_out})
    order = (order_out.get("result") or {}) if order_out.get("ok") else {}
    refund_out = run_tool(
      "calc_refund",
      message,
      amount=order.get("amount"),
      days_since_purchase=order.get("days_since_purchase"),
      order_id=order.get("order_id"),
    )
    tools_log.append({"name": "calc_refund", "output": refund_out})
    result = refund_out.get("result") or {}
    confirmation_id = str(uuid.uuid4())
    pending = {
      "id": confirmation_id,
      "action": "refund_execute",
      "title": "退款执行待确认",
      "detail": refund_out.get("summary", ""),
      "payload": result,
      "demo": True,
    }
    store = _load_pending()
    store[confirmation_id] = {
      "company_id": company_id,
      "conversation_id": conv.id,
      "customer_name": customer_name,
      "payload": result,
      "status": "pending",
    }
    _save_pending(store)

    answer = (
      f"{refund_out.get('summary', '')}\n\n"
      "请点击下方「确认提交给人工」后，坐席将按演示流程处理；"
      "系统不会自动打款。"
    )
    confidence = 0.75
    need_human = True  # 最终仍需人，但不立刻改 waiting，除非确认
    ai_msg = _save_ai_message(db, conv, answer, confidence, [])
    plan_steps.extend([
      {
        "id": "query_order",
        "title": "关联演示订单",
        "status": "done" if order_out.get("ok") else "pending",
        "detail": order_out.get("summary", "无单号时使用默认演示单"),
        "demo": True,
      },
      {
        "id": "calc_refund",
        "title": "退款试算",
        "status": "done",
        "detail": f"建议退 ¥{result.get('refund_amount', 0)}",
        "demo": True,
      },
      {
        "id": "hitl",
        "title": "待人工确认执行",
        "status": "needs_confirm",
        "detail": "高风险动作，需买家确认后进入坐席队列",
        "demo": False,
      },
    ])

  else:
    # consult — 现有 RAG
    ai_msg, answer, confidence, need_human, sources_data, rag_plan = _run_consult(
      db, company_id, conv, message, company_settings, threshold
    )
    plan_steps = rag_plan

  db.commit()
  append_trace({
    "conversation_id": conv.id,
    "company_id": company_id,
    "input": message,
    "intent": intent,
    "tools": [
      {"name": t["name"], "summary": (t.get("output") or {}).get("summary"), "source": (t.get("output") or {}).get("source")}
      for t in tools_log
    ],
    "output": answer,
    "needs_human": need_human,
    "pending_confirmation_id": pending["id"] if pending else None,
  })

  return _base_result(
    conv,
    ai_msg,
    answer=answer,
    confidence=confidence,
    need_human=need_human,
    sources=sources_data,
    intent=intent,
    plan_steps=plan_steps,
    pending_confirmation=pending,
    human_mode=_is_human_mode(db, conv),
  )


def confirm_pending_action(
  db: Session,
  company_id: int,
  confirmation_id: str,
  conversation_id: int | None = None,
  customer_name: str = "访客",
) -> dict:
  store = _load_pending()
  item = store.get(confirmation_id)
  if not item or item.get("company_id") != company_id:
    raise ValueError("确认单不存在或已失效")
  if item.get("status") != "pending":
    raise ValueError("该确认单已处理")

  conv = get_or_create_conversation(
    db, company_id, conversation_id or item.get("conversation_id"), customer_name
  )
  payload = item.get("payload") or {}
  item["status"] = "confirmed"
  store[confirmation_id] = item
  _save_pending(store)

  conv.status = "waiting_human"
  answer = (
    f"【演示】已收到您的确认：建议退款 ¥{payload.get('refund_amount', 0)} "
    f"（订单 {payload.get('order_id', 'DEMO')}）。"
    "已转入人工队列，坐席将继续处理。系统未自动打款。"
  )
  ai_msg = _save_ai_message(db, conv, answer, 0.9, [])
  append_trace({
    "conversation_id": conv.id,
    "company_id": company_id,
    "input": f"[confirm] {confirmation_id}",
    "intent": {"intent": "action", "label": "操作类", "source": "hitl_confirm"},
    "tools": [],
    "output": answer,
    "needs_human": True,
    "pending_confirmation_id": confirmation_id,
    "confirmed": True,
  })
  return {
    "conversation_id": conv.id,
    "message_id": ai_msg.id,
    "answer": answer,
    "confidence": 0.9,
    "need_human": True,
    "human_mode": True,
    "sources": [],
    "intent": "action",
    "intent_label": "操作类",
    "plan_steps": [
      {"id": "hitl", "title": "人工确认", "status": "done", "detail": "买家已确认，已进待人工", "demo": True}
    ],
    "pending_confirmation": None,
  }
