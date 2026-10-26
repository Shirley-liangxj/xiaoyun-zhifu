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
  # 买家看到的是客服话术（role="agent" 买家端可见）；
  # 「演示/审核单/未打款」等内部语义写进 meta.internal_note 只给坐席看
  if decision == "approved":
    content = (
      "好消息！您的退货申请已经通过审核啦，"
      "退款会按您原来的支付方式退回，一般 1-3 个工作日内到账，请注意查收。"
      "还有其他问题随时找我～"
    )
    internal_note = f"审核通过：订单 {order_id} 退款 ¥{amount}（演示：仅记录结果，未执行真实打款）"
    conv.status = "active"
  elif decision == "rejected":
    content = "很抱歉，这次没能帮您通过退货审核。"
    if action.review_note:
      content += f"原因是：{action.review_note}。"
    content += "如果您还有疑问，我很乐意再帮您看看。"
    internal_note = f"审核驳回：订单 {order_id} 退款 ¥{amount}，原因：{action.review_note or '未填写'}"
    conv.status = "active"
  else:
    content = "为了让售后同事帮您准确处理，还需要您补充一点信息。"
    if action.review_note:
      content += f"麻烦补充一下：{action.review_note}。"
    internal_note = f"需补充信息：订单 {order_id}，需补充：{action.review_note or '未填写'}"
    conv.status = "waiting_human"

  db.add(Message(
    conversation_id=conv.id,
    sender_id=reviewer_id,
    role="agent",
    content=content,
    is_sent=True,
    meta=json.dumps({"internal_note": internal_note}, ensure_ascii=False),
  ))
  db.commit()
  db.refresh(action)
  return action
