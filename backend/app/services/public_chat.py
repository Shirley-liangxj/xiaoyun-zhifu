"""买家端公开对话服务 - RAG + LLM 回答"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Conversation, Message
from app.services.ai_suggestion import _build_context, _calc_confidence
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


def chat_for_buyer(
  db: Session,
  company_id: int,
  message: str,
  conversation_id: int | None = None,
  customer_name: str = "访客",
) -> dict:
  """买家公开对话：检索知识库 → 生成回答 → 返回溯源与置信度"""
  company_settings = get_or_create_settings(db, company_id)
  threshold = company_settings.confidence_threshold

  # 获取或创建会话
  if conversation_id:
    conv = db.query(Conversation).filter(
      Conversation.id == conversation_id,
      Conversation.company_id == company_id,
    ).first()
    if not conv:
      conv = None
  else:
    conv = None

  if not conv:
    conv = Conversation(company_id=company_id, customer_name=customer_name, channel="web")
    db.add(conv)
    db.commit()
    db.refresh(conv)

  # 保存客户消息
  db.add(Message(conversation_id=conv.id, role="customer", content=message, is_sent=True))
  db.commit()

  # RAG 检索
  try:
    sources = search_knowledge(company_id, message, top_k=3)
  except Exception:
    sources = []

  confidence = _calc_confidence(sources)
  need_human = confidence < threshold or not sources

  sources_data = [
    {"doc_id": s["doc_id"], "title": s["title"], "category": s["category"], "text": s["text"], "score": s["score"]}
    for s in sources
  ]

  if need_human:
    answer = company_settings.reject_message or "抱歉，这个问题我需要为您转接人工客服，请稍候。"
    role = "ai_suggestion"
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
    except ValueError:
      answer = "AI 服务暂不可用，已为您转接人工客服。"
      need_human = True
    role = "ai_suggestion"

  # 保存 AI 回复
  ai_msg = Message(
    conversation_id=conv.id,
    role=role,
    content=answer.strip(),
    confidence=confidence,
    sources=json.dumps(sources_data, ensure_ascii=False),
    is_sent=True,
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
    "sources": sources_data,
  }
