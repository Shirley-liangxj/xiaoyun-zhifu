"""数据统计路由 - Dashboard 看板数据"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Conversation, KnowledgeDoc, Message, Ticket, User
from app.schemas.stats import (
  DashboardStats,
  OverviewStats,
  PriorityBreakdown,
  TicketStatusBreakdown,
)

router = APIRouter(prefix="/api/stats", tags=["数据统计"])


@router.get("/dashboard", response_model=DashboardStats, summary="Dashboard 统计数据")
def get_dashboard_stats(
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """获取工作台所需的全部统计数据"""
  company_id = current_user.company_id

  # 会话统计
  total_convs = db.query(func.count(Conversation.id)).filter(
    Conversation.company_id == company_id
  ).scalar() or 0
  active_convs = db.query(func.count(Conversation.id)).filter(
    Conversation.company_id == company_id,
    Conversation.status == "active",
  ).scalar() or 0

  # 消息统计（通过会话关联）
  conv_ids = db.query(Conversation.id).filter(Conversation.company_id == company_id).subquery()
  total_msgs = db.query(func.count(Message.id)).filter(
    Message.conversation_id.in_(conv_ids),
    Message.role.in_(["customer", "agent"]),
  ).scalar() or 0

  # AI 建议统计
  ai_total = db.query(func.count(Message.id)).filter(
    Message.conversation_id.in_(conv_ids),
    Message.role == "ai_suggestion",
  ).scalar() or 0
  ai_accepted = db.query(func.count(Message.id)).filter(
    Message.conversation_id.in_(conv_ids),
    Message.role == "ai_suggestion",
    Message.is_sent == True,
  ).scalar() or 0
  accept_rate = round(ai_accepted / ai_total * 100, 1) if ai_total > 0 else 0.0

  # 工单统计
  total_tickets = db.query(func.count(Ticket.id)).filter(
    Ticket.company_id == company_id
  ).scalar() or 0

  def ticket_count_by_status(s):
    return db.query(func.count(Ticket.id)).filter(
      Ticket.company_id == company_id, Ticket.status == s
    ).scalar() or 0

  def ticket_count_by_priority(p):
    return db.query(func.count(Ticket.id)).filter(
      Ticket.company_id == company_id, Ticket.priority == p
    ).scalar() or 0

  # 知识库统计
  total_docs = db.query(func.count(KnowledgeDoc.id)).filter(
    KnowledgeDoc.company_id == company_id
  ).scalar() or 0
  indexed_docs = db.query(func.count(KnowledgeDoc.id)).filter(
    KnowledgeDoc.company_id == company_id,
    KnowledgeDoc.is_indexed == True,
  ).scalar() or 0

  return DashboardStats(
    overview=OverviewStats(
      total_conversations=total_convs,
      active_conversations=active_convs,
      total_messages=total_msgs,
      total_tickets=total_tickets,
      open_tickets=ticket_count_by_status("open"),
      in_progress_tickets=ticket_count_by_status("in_progress"),
      resolved_tickets=ticket_count_by_status("resolved"),
      total_knowledge_docs=total_docs,
      indexed_docs=indexed_docs,
      ai_suggestions=ai_total,
      ai_accepted=ai_accepted,
      ai_accept_rate=accept_rate,
    ),
    ticket_status=TicketStatusBreakdown(
      open=ticket_count_by_status("open"),
      in_progress=ticket_count_by_status("in_progress"),
      resolved=ticket_count_by_status("resolved"),
      closed=ticket_count_by_status("closed"),
    ),
    ticket_priority=PriorityBreakdown(
      low=ticket_count_by_priority("low"),
      normal=ticket_count_by_priority("normal"),
      high=ticket_count_by_priority("high"),
      urgent=ticket_count_by_priority("urgent"),
    ),
  )
