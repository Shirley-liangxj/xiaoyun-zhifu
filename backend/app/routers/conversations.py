"""会话路由 - 会话与消息管理 + AI 回复建议"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Conversation, HumanReviewAction, HumanReviewEvent, Message, User
from app.schemas.conversation import (
  AcceptSuggestionRequest,
  ConversationCreate,
  ConversationDetail,
  ConversationOut,
  MessageCreate,
  MessageOut,
)
from app.schemas.human_review import HumanReviewDecision, HumanReviewOut
from app.services.human_review import decide_review_action, list_review_actions
from app.services.ai_suggestion import generate_suggestion
from app.services.knowledge_gap import record_knowledge_gap
from app.services.settings import get_or_create_settings

router = APIRouter(prefix="/api/conversations", tags=["会话"])
logger = logging.getLogger(__name__)


def _review_out(db: Session, action: HumanReviewAction) -> HumanReviewOut:
  try:
    payload = json.loads(action.payload or "{}")
  except json.JSONDecodeError:
    payload = {}
  events = db.query(HumanReviewEvent).filter(
    HumanReviewEvent.action_id == action.id,
    HumanReviewEvent.company_id == action.company_id,
  ).order_by(HumanReviewEvent.created_at.asc()).all()
  return HumanReviewOut(
    id=action.id,
    conversation_id=action.conversation_id,
    customer_name=action.customer_name,
    action=action.action,
    title=action.title,
    detail=action.detail or "",
    payload=payload,
    status=action.status,
    risk_reason=action.risk_reason or "",
    buyer_confirmed_at=action.buyer_confirmed_at,
    reviewer_id=action.reviewer_id,
    reviewed_at=action.reviewed_at,
    review_note=action.review_note or "",
    created_at=action.created_at,
    events=events,
  )


def _build_conversation_out(conv: Conversation, db: Session) -> ConversationOut:
  """构建会话列表项（含消息统计）"""
  msg_count = db.query(func.count(Message.id)).filter(
    Message.conversation_id == conv.id,
    Message.role.in_(["customer", "agent"]),
  ).scalar() or 0

  last_msg = db.query(Message).filter(
    Message.conversation_id == conv.id,
    Message.role.in_(["customer", "agent", "ai_suggestion"]),
  ).order_by(Message.created_at.desc()).first()

  unread_q = db.query(func.count(Message.id)).filter(
    Message.conversation_id == conv.id,
    Message.role == "customer",
  )
  if conv.agent_last_read_at:
    unread_q = unread_q.filter(Message.created_at > conv.agent_last_read_at)
  unread_count = unread_q.scalar() or 0

  return ConversationOut(
    id=conv.id,
    customer_name=conv.customer_name,
    channel=conv.channel,
    status=conv.status,
    created_at=conv.created_at,
    closed_at=conv.closed_at,
    message_count=msg_count,
    last_message=last_msg.content[:80] if last_msg else None,
    last_message_at=last_msg.created_at if last_msg else conv.created_at,
    unread_count=unread_count,
  )


@router.get("/", response_model=list[ConversationOut], summary="获取会话列表")
def list_conversations(
  status_filter: str | None = None,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """获取当前公司的会话列表，可按状态筛选"""
  query = db.query(Conversation).filter(
    Conversation.company_id == current_user.company_id
  )
  if status_filter:
    query = query.filter(Conversation.status == status_filter)
  convs = query.order_by(
    case(
      (Conversation.status == "waiting_human", 0),
      (Conversation.status == "active", 1),
      else_=2,
    ),
    Conversation.created_at.desc(),
  ).all()
  return [_build_conversation_out(c, db) for c in convs]


@router.post("/", response_model=ConversationOut, summary="创建新会话")
def create_conversation(
  body: ConversationCreate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """创建新的客户咨询会话"""
  conv = Conversation(
    company_id=current_user.company_id,
    customer_name=body.customer_name,
    channel=body.channel,
  )
  db.add(conv)
  db.commit()
  db.refresh(conv)
  return _build_conversation_out(conv, db)


@router.get("/{conversation_id}", response_model=ConversationDetail, summary="获取会话详情")
def get_conversation(
  conversation_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """获取会话详情及全部消息"""
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == current_user.company_id,
  ).first()
  if not conv:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

  conv.agent_last_read_at = datetime.utcnow()
  db.commit()
  db.refresh(conv)

  messages = db.query(Message).filter(
    Message.conversation_id == conv.id
  ).order_by(Message.created_at.asc()).all()

  base = _build_conversation_out(conv, db)
  return ConversationDetail(
    **base.model_dump(),
    messages=[MessageOut.model_validate(m) for m in messages],
  )


@router.post("/{conversation_id}/messages", response_model=MessageOut, summary="发送消息")
def send_message(
  conversation_id: int,
  body: MessageCreate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """发送消息；客户消息发送后自动生成 AI 回复建议"""
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == current_user.company_id,
  ).first()
  if not conv:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
  if conv.status == "closed":
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会话已关闭")

  sender_id = current_user.id if body.role == "agent" else None
  msg = Message(
    conversation_id=conv.id,
    sender_id=sender_id,
    role=body.role,
    content=body.content,
    is_sent=True,
  )
  if body.role == "agent" and conv.status == "waiting_human":
    conv.status = "active"

  db.add(msg)
  db.commit()
  db.refresh(msg)

  # 客户消息后自动生成 AI 回复建议
  if body.role == "customer":
    settings = get_or_create_settings(db, current_user.company_id)
    if settings.auto_suggest:
      try:
        suggestion = generate_suggestion(db, conv, body.content)
        record_knowledge_gap(db, conv.company_id, body.content, suggestion.confidence or 0, settings.confidence_threshold)
      except Exception as e:
        logger.warning("AI suggestion failed for conversation %s: %s", conv.id, e)

  return msg


@router.post("/{conversation_id}/ai-suggest", response_model=MessageOut, summary="手动触发 AI 建议")
def trigger_ai_suggestion(
  conversation_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """基于最新客户消息重新生成 AI 回复建议"""
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == current_user.company_id,
  ).first()
  if not conv:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

  # 找最新客户消息
  last_customer_msg = db.query(Message).filter(
    Message.conversation_id == conv.id,
    Message.role == "customer",
  ).order_by(Message.created_at.desc()).first()

  if not last_customer_msg:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="暂无客户消息，无法生成建议")

  # 移除未处理的旧建议
  db.query(Message).filter(
    Message.conversation_id == conv.id,
    Message.role == "ai_suggestion",
    Message.is_sent == False,
  ).delete()
  db.commit()

  suggestion = generate_suggestion(db, conv, last_customer_msg.content)
  return suggestion


@router.post("/{conversation_id}/suggestions/{suggestion_id}/accept", response_model=MessageOut, summary="采纳 AI 建议")
def accept_suggestion(
  conversation_id: int,
  suggestion_id: int,
  body: AcceptSuggestionRequest = AcceptSuggestionRequest(),
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """采纳 AI 建议并作为坐席消息发送（可编辑内容）"""
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == current_user.company_id,
  ).first()
  if not conv:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
  if conv.status == "closed":
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会话已关闭")

  suggestion = db.query(Message).filter(
    Message.id == suggestion_id,
    Message.conversation_id == conv.id,
    Message.role == "ai_suggestion",
    Message.is_sent == False,
  ).first()
  if not suggestion:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="建议不存在或已处理")

  original_content = suggestion.content.strip()
  content = body.content.strip() if body.content else original_content

  # 创建坐席消息
  agent_msg = Message(
    conversation_id=conv.id,
    sender_id=current_user.id,
    role="agent",
    content=content,
    is_sent=True,
  )
  db.add(agent_msg)

  # 标记建议已处理
  suggestion.is_sent = True
  suggestion.suggestion_status = (
    "edited_and_accepted" if content != original_content else "accepted"
  )
  if conv.status == "waiting_human":
    conv.status = "active"
  db.commit()
  db.refresh(agent_msg)
  return agent_msg


@router.get("/{conversation_id}/reviews", response_model=list[HumanReviewOut], summary="获取会话审核单")
def list_conversation_reviews(
  conversation_id: int,
  status_filter: str | None = None,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == current_user.company_id,
  ).first()
  if not conv:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
  actions = list_review_actions(
    db,
    company_id=current_user.company_id,
    conversation_id=conversation_id,
    status_filter=status_filter,
  )
  return [_review_out(db, action) for action in actions]


@router.post("/{conversation_id}/reviews/{review_id}/decision", response_model=HumanReviewOut, summary="坐席审核退款建议")
def decide_conversation_review(
  conversation_id: int,
  review_id: str,
  body: HumanReviewDecision,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  try:
    action = decide_review_action(
      db,
      company_id=current_user.company_id,
      conversation_id=conversation_id,
      review_id=review_id,
      reviewer_id=current_user.id,
      decision=body.decision,
      note=body.note,
    )
  except ValueError as exc:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
  return _review_out(db, action)


@router.post("/{conversation_id}/suggestions/{suggestion_id}/reject", summary="忽略 AI 建议")
def reject_suggestion(
  conversation_id: int,
  suggestion_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """忽略/拒绝 AI 回复建议"""
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == current_user.company_id,
  ).first()
  if not conv:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

  suggestion = db.query(Message).filter(
    Message.id == suggestion_id,
    Message.conversation_id == conv.id,
    Message.role == "ai_suggestion",
    Message.is_sent == False,
  ).first()
  if not suggestion:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="建议不存在或已处理")

  suggestion.suggestion_status = "rejected"
  suggestion.is_sent = True
  db.commit()
  return {"message": "已忽略该建议", "id": suggestion_id}


@router.post("/{conversation_id}/accept", summary="坐席接入待人工会话")
def accept_conversation(
  conversation_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """将 waiting_human 会话接入为 active，并发送接入提示。"""
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == current_user.company_id,
  ).first()
  if not conv:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
  if conv.status == "closed":
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会话已关闭")
  if conv.status != "waiting_human":
    return {"message": "会话已在处理中", "id": conversation_id, "status": conv.status}

  waiting_review = db.query(HumanReviewAction).filter(
    HumanReviewAction.company_id == current_user.company_id,
    HumanReviewAction.conversation_id == conversation_id,
    HumanReviewAction.status == "waiting_review",
  ).first()
  if waiting_review:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="该会话有待审核退款建议，请先在审核卡中批准、拒绝或要求补充材料",
    )

  conv.status = "active"
  tip = Message(
    conversation_id=conv.id,
    sender_id=current_user.id,
    role="agent",
    content="您好，人工客服已接入，请问还有什么可以帮您？",
    is_sent=True,
  )
  db.add(tip)
  db.commit()
  return {"message": "已接入", "id": conversation_id, "status": conv.status}


@router.post("/{conversation_id}/close", summary="关闭会话")
def close_conversation(
  conversation_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """关闭会话"""
  conv = db.query(Conversation).filter(
    Conversation.id == conversation_id,
    Conversation.company_id == current_user.company_id,
  ).first()
  if not conv:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

  conv.status = "closed"
  conv.closed_at = datetime.utcnow()
  db.commit()
  return {"message": "会话已关闭", "id": conversation_id}
