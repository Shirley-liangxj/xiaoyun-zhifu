"""坐席审核状态机与审计记录。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Conversation, HumanReviewAction, HumanReviewEvent, Message


REVIEW_DECISIONS = {"approved", "rejected", "need_more_info"}


def add_review_event(
  db: Session,
  action: HumanReviewAction,
  *,
  from_status: str,
  to_status: str,
  actor_type: str,
  actor_id: int | None = None,
  note: str = "",
) -> HumanReviewEvent:
  event = HumanReviewEvent(
    action_id=action.id,
    company_id=action.company_id,
    conversation_id=action.conversation_id,
    from_status=from_status,
    to_status=to_status,
    actor_type=actor_type,
    actor_id=actor_id,
    note=note,
  )
  db.add(event)
  return event


def list_review_actions(
  db: Session,
  *,
  company_id: int,
  conversation_id: int | None = None,
  status_filter: str | None = None,
) -> list[HumanReviewAction]:
  query = db.query(HumanReviewAction).filter(HumanReviewAction.company_id == company_id)
  if conversation_id is not None:
    query = query.filter(HumanReviewAction.conversation_id == conversation_id)
  if status_filter:
    query = query.filter(HumanReviewAction.status == status_filter)
  return query.order_by(HumanReviewAction.created_at.desc()).all()


def decide_review_action(
  db: Session,
  *,
  company_id: int,
  conversation_id: int,
  review_id: str,
  reviewer_id: int,
  decision: str,
  note: str = "",
) -> HumanReviewAction:
  if decision not in REVIEW_DECISIONS:
    raise ValueError("审核结果必须是 approved、rejected 或 need_more_info")

  action = db.query(HumanReviewAction).filter(
    HumanReviewAction.id == review_id,
    HumanReviewAction.company_id == company_id,
    HumanReviewAction.conversation_id == conversation_id,
  ).first()
  if not action:
    raise ValueError("审核单不存在或不属于当前会话")
  if action.status != "waiting_review":
    raise ValueError("该审核单已完成审核或尚未由买家确认")

  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == company_id,
  ).first()
  if not conv:
    raise ValueError("会话不存在")

  from_status = action.status
  action.status = decision
  action.reviewer_id = reviewer_id
  action.reviewed_at = datetime.utcnow()
  action.resolved_at = action.reviewed_at
  action.review_note = note.strip()
  add_review_event(
    db,
    action,
    from_status=from_status,
    to_status=decision,
    actor_type="agent",
    actor_id=reviewer_id,
    note=action.review_note,
  )

  try:
    payload = json.loads(action.payload or "{}")
  except json.JSONDecodeError:
    payload = {}
  amount = payload.get("refund_amount", 0)
  order_id = payload.get("order_id", "未提供")
  if decision == "approved":
    content = (
      f"【演示审核】订单 {order_id} 的退款建议（¥{amount}）已由人工审核通过。"
      "本项目只记录审核结果，未执行真实退款。"
    )
    conv.status = "active"
  elif decision == "rejected":
    content = "【演示审核】退款建议未通过人工审核。"
    if action.review_note:
      content += f"原因：{action.review_note}。"
    content += "本项目未执行真实退款。"
    conv.status = "active"
  else:
    content = "【演示审核】坐席需要您补充信息后再审核。"
    if action.review_note:
      content += f"请补充：{action.review_note}。"
    conv.status = "waiting_human"

  db.add(Message(
    conversation_id=conv.id,
    sender_id=reviewer_id,
    role="agent",
    content=content,
    is_sent=True,
  ))
  db.commit()
  db.refresh(action)
  return action
