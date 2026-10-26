"""买家端公开对话服务 - RAG + LLM 回答 / 转人工"""
from __future__ import annotations

import json
from pathlib import Path

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
  if getattr(msg, "is_internal", False):
    return False
  if msg.role in ("customer", "agent"):
    return True
  if msg.role == "ai_suggestion" and msg.is_sent:
    return msg.suggestion_status in (None, "auto_sent", "legacy_sent")
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


def parse_meta(raw: str | None) -> dict:
  """消息结构化元数据：执行计划 / 待确认动作 / 业务卡片"""
  if not raw:
    return {}
  try:
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}
  except Exception:
    return {}


# —— 买家端白名单 ——
# 原则：买家的屏幕上只该有「客服说的话」+「能看懂的订单卡片」+「一个明确的操作按钮」。
# 执行计划、工具名、规则理由、检索来源、置信度、内部备注一律不下发（不是前端隐藏，是后端不给）。
BUYER_ACTION_LABELS = {
  "refund_review": "提交退货申请",
}

_CARD_FIELDS = ("type", "order_id", "product", "status", "express", "tracking_no", "logistics", "amount")


def buyer_card(card: dict | None) -> dict | None:
  """订单卡片：只保留买家看得懂的业务字段，去掉 demo 等内部标记。"""
  if not isinstance(card, dict) or not card:
    return None
  out = {k: card.get(k) for k in _CARD_FIELDS}
  if not out.get("order_id"):
    return None
  out["type"] = out.get("type") or "order"
  return out


def buyer_action(pending: dict | None) -> dict | None:
  """待确认动作：只给按钮文案，不给 action 类型、风险说明、payload。"""
  if not isinstance(pending, dict) or not pending.get("id"):
    return None
  action = str(pending.get("action") or "")
  return {
    "id": pending["id"],
    "label": BUYER_ACTION_LABELS.get(action, "确认提交"),
  }


def serialize_message(msg: Message) -> dict:
  meta = parse_meta(getattr(msg, "meta", None))
  display_role = "assistant"
  if msg.role == "customer":
    display_role = "user"
  elif msg.role == "agent":
    display_role = "agent"
  return {
    "id": msg.id,
    "role": display_role,
    "content": msg.content,
    "created_at": msg.created_at.isoformat() if msg.created_at else None,
    "card": buyer_card(meta.get("card")),
    "action": buyer_action(meta.get("pending_confirmation")),
  }


def buyer_response(result: dict) -> dict:
  """把 agent 的内部结果压成买家视图（白名单，多余字段直接丢弃）。"""
  return {
    "conversation_id": result.get("conversation_id"),
    "message_id": result.get("message_id", 0),
    "answer": result.get("answer", ""),
    "need_human": bool(result.get("need_human")),
    "human_mode": bool(result.get("human_mode")),
    "card": buyer_card(result.get("card")),
    "action": buyer_action(result.get("pending_confirmation")),
  }


ORDERS_PATH = Path(__file__).resolve().parents[1] / "data" / "orders_demo.json"

# 订单列表允许下发给买家的字段（白名单，和 buyer_card 同口径）
_ORDER_LIST_FIELDS = ("order_id", "product", "status", "express", "tracking_no", "amount")


def list_buyer_orders(company_id: int, customer_name: str) -> list[dict]:
  """按昵称匹配演示订单，返回「我的订单」列表（买家视图）。

  演示环境没有真实账号体系，用 customer_hint 做归属匹配：
  昵称包含 hint 或 hint 包含昵称即算匹配；匹配不到时返回全部演示订单
  （保证买家端永远有得可点，由坐席侧标注「演示」区分）。
  """
  try:
    raw = json.loads(ORDERS_PATH.read_text(encoding="utf-8"))
  except Exception:
    return []
  name = (customer_name or "").strip()
  matched, fallback = [], []
  for o in raw:
    item = {k: o.get(k) for k in _ORDER_LIST_FIELDS}
    if not item.get("order_id"):
      continue
    fallback.append(item)
    hint = (o.get("customer_hint") or "").strip()
    if name and hint and (hint in name or name in hint):
      matched.append(item)
  return matched or fallback


def resolve_conversation(db: Session, company_id: int, conversation_id: int, customer_name: str) -> dict:
  """买家确认问题解决 → 会话收尾（closed + 结束语）。旅程终点，消除「戛然而止」。"""
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == company_id,
  ).first()
  if not conv:
    raise ValueError("会话不存在")
  if conv.status == "closed":
    return {"conversation_id": conv.id, "status": "closed", "message_id": 0, "already": True}
  conv.status = "closed"
  end_msg = Message(
    conversation_id=conv.id,
    role="ai_suggestion",
    content="好的，如果后续还有任何问题，随时回来找我，祝您生活愉快～",
    confidence=1.0,
    sources="[]",
    is_sent=True,
    suggestion_status="auto_sent",
  )
  db.add(end_msg)
  db.commit()
  db.refresh(end_msg)
  return {
    "conversation_id": conv.id,
    "status": "closed",
    "message_id": end_msg.id,
    "answer": end_msg.content,
    "need_human": False,
    "human_mode": False,
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
    suggestion_status="auto_sent",
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
    suggestion_status="auto_sent",
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
