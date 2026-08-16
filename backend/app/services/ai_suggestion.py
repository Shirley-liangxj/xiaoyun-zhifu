"""AI 回复建议服务 - RAG 检索 + LLM 生成 + 置信度评分"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Conversation, Message
from app.services.llm import llm_service
from app.services.rag import search_knowledge

# 系统提示词
SYSTEM_PROMPT = """你是一名专业的服饰电商售后客服助手。请根据提供的知识库参考资料和对话历史，为客户问题生成简洁、专业、友好的回复建议。

要求：
1. 回复语气亲切专业，适合服饰电商场景
2. 优先依据知识库参考资料回答，不要编造政策
3. 如果参考资料不足以回答，诚实说明需要进一步核实
4. 回复控制在 150 字以内
5. 只输出回复内容本身，不要加前缀或解释"""


def _build_context(sources: list[dict]) -> str:
  """将 RAG 检索结果格式化为参考资料文本"""
  if not sources:
    return "（暂无相关知识库参考资料）"
  parts = []
  for i, s in enumerate(sources, 1):
    parts.append(f"[{i}] 《{s['title']}》（{s['category']}）\n{s['text']}")
  return "\n\n".join(parts)


def _build_history(messages: list[Message], limit: int = 10) -> str:
  """将最近对话历史格式化为文本"""
  recent = [m for m in messages if m.role in ("customer", "agent")][-limit:]
  if not recent:
    return "（暂无对话历史）"
  role_map = {"customer": "客户", "agent": "坐席"}
  lines = [f"{role_map.get(m.role, m.role)}：{m.content}" for m in recent]
  return "\n".join(lines)


def _calc_confidence(sources: list[dict]) -> float:
  """
  基于 RAG 检索结果计算置信度（0~1）。
  - 无检索结果：0.25
  - 有结果：取 top-3 平均相似度，映射到 0.4~0.95
  """
  if not sources:
    return 0.25
  top_scores = [s["score"] for s in sources[:3]]
  avg_score = sum(top_scores) / len(top_scores)
  # 相似度通常在 0.3~0.9，映射到置信度
  confidence = 0.4 + avg_score * 0.55
  return round(min(max(confidence, 0.1), 0.95), 2)


def generate_suggestion(
  db: Session,
  conversation: Conversation,
  customer_message: str,
) -> Message:
  """
  为客户消息生成 AI 回复建议：
  1. RAG 检索知识库
  2. 构建 prompt 调用 GLM-4-Flash
  3. 计算置信度
  4. 保存 ai_suggestion 消息
  """
  # RAG 检索
  try:
    sources = search_knowledge(conversation.company_id, customer_message, top_k=3)
  except Exception:
    sources = []

  confidence = _calc_confidence(sources)

  # 获取对话历史
  all_messages = db.query(Message).filter(
    Message.conversation_id == conversation.id
  ).order_by(Message.created_at.asc()).all()

  context = _build_context(sources)
  history = _build_history(all_messages)

  # 构建 LLM 请求
  user_prompt = f"""## 知识库参考资料
{context}

## 对话历史
{history}

## 客户最新问题
{customer_message}

请生成回复建议："""

  try:
    reply = llm_service.chat([
      {"role": "system", "content": SYSTEM_PROMPT},
      {"role": "user", "content": user_prompt},
    ])
  except ValueError:
    # API Key 未配置，生成占位建议
    reply = "（AI 服务未配置，请在 .env 中设置 LLM_API_KEY 后重试）"
    confidence = 0.0

  # 来源溯源 JSON
  sources_json = json.dumps([
    {"doc_id": s["doc_id"], "title": s["title"], "category": s["category"], "score": s["score"]}
    for s in sources
  ], ensure_ascii=False)

  suggestion = Message(
    conversation_id=conversation.id,
    role="ai_suggestion",
    content=reply.strip(),
    confidence=confidence,
    sources=sources_json,
    is_sent=False,
  )
  db.add(suggestion)
  db.commit()
  db.refresh(suggestion)
  return suggestion
