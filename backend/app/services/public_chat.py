"""买家端公开对话服务 - RAG + LLM 回答 / 转人工"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import Conversation, Message
from app.services.ai_suggestion import _build_context, _calc_confidence, generate_suggestion
from app.services.errors import ExternalServiceError
from app.services.knowledge_gap import record_knowledge_gap
from app.services.llm import llm_service
from app.services.rag import search_knowledge
from app.services.settings import get_or_create_settings

BUYER_SYSTEM_PROMPT = """你是「云裳服饰」店铺的售后 AI 客服「小云」，负责回答买家关于退换货、运费、物流、尺码、质量问题的咨询。

要求：
1. 只依据提供的政策资料回答，禁止编造
2. 语气亲切口语化，直接给结论
3. 涉及例外条款（定制/预售/贴身衣物）必须说明
4. 控制在 150 字以内
5. 资料不足时明确说明并建议转人工"""

TRANSFER_NOTE = "已为您转接人工客服，坐席正在接入，请稍候。"


def _visible_to_buyer(msg: Message) -> bool:
  if msg.role in ("customer", "agent"):
    return True
  if msg.role == "ai_suggestion" and msg.is_sent:
    return True
  return False


def get_or_create_conversation(
  db: Session,
  company_id: int,
  conversation_id: int | None,
  customer_name: str,
) -> Conversation:
  conv = None
  name = (customer_name or "").strip() or "访客"
  if conversation_id:
    conv = db.query(Conversation).filter(
      Conversation.id == conversation_id,
      Conversation.company_id == company_id,
    ).first()
  if not conv:
    conv = Conversation(company_id=company_id, customer_name=name, channel="web")
    db.add(conv)
    db.commit()
    db.refresh(conv)
  elif name and name != "访客" and (not conv.customer_name or conv.customer_name == "访客"):
    conv.customer_name = name
    db.commit()
  return conv


def _is_human_mode(db: Session, conv: Conversation) -> bool:
  """待人工，或已有坐席介入的进行中会话，均视为人工模式。"""
  if conv.status == "waiting_human":
    return True
  if conv.status == "closed":
    return False
  has_agent = db.query(Message.id).filter(
    Message.conversation_id == conv.id,
    Message.role == "agent",
  ).first()
  return has_agent is not None


def serialize_message(msg: Message) -> dict:
  sources = []
  if msg.sources:
    try:
      sources = json.loads(msg.sources)
    except Exception:
      sources = []
  display_role = "assistant"
  if msg.role == "customer":
    display_role = "user"
  elif msg.role == "agent":
    display_role = "agent"
  elif msg.role == "ai_suggestion":
    display_role = "assistant"
  return {
    "id": msg.id,
    "role": display_role,
    "content": msg.content,
    "confidence": msg.confidence,
    "sources": sources,
    "created_at": msg.created_at.isoformat() if msg.created_at else None,
  }


def list_buyer_messages(db: Session, company_id: int, conversation_id: int) -> dict:
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == company_id,
  ).first()
  if not conv:
    return {"conversation_id": conversation_id, "status": "missing", "human_mode": False, "messages": []}
  messages = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
  return {
    "conversation_id": conv.id,
    "status": conv.status,
    "human_mode": _is_human_mode(db, conv),
    "messages": [serialize_message(m) for m in messages if _visible_to_buyer(m)],
  }


def transfer_to_human(db: Session, company_id: int, conversation_id: int | None, customer_name: str = "访客") -> dict:
  conv = get_or_create_conversation(db, company_id, conversation_id, customer_name)
  conv.status = "waiting_human"
  company_settings = get_or_create_settings(db, company_id)
  answer = company_settings.reject_message or TRANSFER_NOTE
  ai_msg = Message(
    conversation_id=conv.id,
    role="ai_suggestion",
    content=answer,
    confidence=0.2,
    sources="[]",
    is_sent=True,
  )
  db.add(ai_msg)
  db.commit()
  db.refresh(ai_msg)
  return {
    "conversation_id": conv.id,
    "message_id": ai_msg.id,
    "answer": ai_msg.content,
    "confidence": 0.2,
    "need_human": True,
    "human_mode": True,
    "sources": [],
  }


def chat_for_buyer(
  db: Session,
  company_id: int,
  message: str,
  conversation_id: int | None = None,
  customer_name: str = "访客",
) -> dict:
  """买家公开对话：检索知识库 → 生成回答；低置信或已转人工则进入坐席队列。"""
  company_settings = get_or_create_settings(db, company_id)
  threshold = company_settings.confidence_threshold
  conv = get_or_create_conversation(db, company_id, conversation_id, customer_name)

  db.add(Message(conversation_id=conv.id, role="customer", content=message, is_sent=True))
  db.commit()

  # 已转人工：只落客户消息，并给坐席生成待采纳建议
  if conv.status == "waiting_human":
    try:
      generate_suggestion(db, conv, message)
    except Exception:
      pass
    return {
      "conversation_id": conv.id,
      "message_id": 0,
      "answer": "",
      "confidence": 0.0,
      "need_human": True,
      "human_mode": True,
      "sources": [],
    }

  try:
    sources = search_knowledge(company_id, message, top_k=3)
  except Exception:
    sources = []

  confidence = _calc_confidence(sources)
  need_human = confidence < threshold or not sources
  record_knowledge_gap(db, company_id, message, confidence, threshold)

  sources_data = [
    {"doc_id": s["doc_id"], "title": s["title"], "category": s["category"], "text": s["text"], "score": s["score"]}
    for s in sources
  ]

  if need_human:
    answer = company_settings.reject_message or TRANSFER_NOTE
    conv.status = "waiting_human"
    role = "ai_suggestion"
    is_sent = True
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
    role = "ai_suggestion"
    is_sent = True

  ai_msg = Message(
    conversation_id=conv.id,
    role=role,
    content=answer.strip(),
    confidence=confidence,
    sources=json.dumps(sources_data, ensure_ascii=False),
    is_sent=is_sent,
  )
  db.add(ai_msg)
  db.commit()
  db.refresh(ai_msg)

  return {
    "conversation_id": conv.id,
    "message_id": ai_msg.id,
    "answer": ai_msg.content,
    "confidence": confidence,
    "need_human": need_human,
    "human_mode": _is_human_mode(db, conv),
    "sources": sources_data,
  }
