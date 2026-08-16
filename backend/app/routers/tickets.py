"""工单路由 - 完整 CRUD + 状态流转"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Conversation, Ticket, User
from app.schemas.ticket import TicketCreate, TicketOut, TicketUpdate

router = APIRouter(prefix="/api/tickets", tags=["工单"])

STATUS_LABELS = {"open": "待处理", "in_progress": "处理中", "resolved": "已解决", "closed": "已关闭"}
PRIORITY_LABELS = {"low": "低", "normal": "普通", "high": "高", "urgent": "紧急"}


def _build_ticket_out(ticket: Ticket) -> TicketOut:
  """构建工单输出（含关联信息）"""
  assignee_name = None
  if ticket.assignee:
    assignee_name = ticket.assignee.display_name or ticket.assignee.username

  customer_name = None
  if ticket.conversation:
    customer_name = ticket.conversation.customer_name

  return TicketOut(
    id=ticket.id,
    title=ticket.title,
    description=ticket.description,
    status=ticket.status,
    priority=ticket.priority,
    conversation_id=ticket.conversation_id,
    assignee_id=ticket.assignee_id,
    assignee_name=assignee_name,
    customer_name=customer_name,
    created_at=ticket.created_at,
    updated_at=ticket.updated_at,
  )


@router.get("/", response_model=list[TicketOut], summary="获取工单列表")
def list_tickets(
  status_filter: str | None = None,
  priority_filter: str | None = None,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """获取当前公司工单列表，支持按状态和优先级筛选"""
  query = db.query(Ticket).filter(Ticket.company_id == current_user.company_id)
  if status_filter:
    query = query.filter(Ticket.status == status_filter)
  if priority_filter:
    query = query.filter(Ticket.priority == priority_filter)
  tickets = query.order_by(Ticket.updated_at.desc()).all()
  return [_build_ticket_out(t) for t in tickets]


@router.post("/", response_model=TicketOut, summary="创建工单")
def create_ticket(
  body: TicketCreate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """创建新工单，可关联会话"""
  if body.conversation_id:
    conv = db.query(Conversation).filter(
      Conversation.id == body.conversation_id,
      Conversation.company_id == current_user.company_id,
    ).first()
    if not conv:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联会话不存在")

  ticket = Ticket(
    company_id=current_user.company_id,
    title=body.title,
    description=body.description,
    priority=body.priority,
    conversation_id=body.conversation_id,
    assignee_id=current_user.id,
    status="open",
  )
  db.add(ticket)
  db.commit()
  db.refresh(ticket)
  return _build_ticket_out(ticket)


@router.get("/{ticket_id}", response_model=TicketOut, summary="获取工单详情")
def get_ticket(
  ticket_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """获取工单详情"""
  ticket = db.query(Ticket).filter(
    Ticket.id == ticket_id,
    Ticket.company_id == current_user.company_id,
  ).first()
  if not ticket:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
  return _build_ticket_out(ticket)


@router.put("/{ticket_id}", response_model=TicketOut, summary="更新工单")
def update_ticket(
  ticket_id: int,
  body: TicketUpdate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """更新工单信息、状态、优先级或指派人"""
  ticket = db.query(Ticket).filter(
    Ticket.id == ticket_id,
    Ticket.company_id == current_user.company_id,
  ).first()
  if not ticket:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")

  if body.title is not None:
    ticket.title = body.title
  if body.description is not None:
    ticket.description = body.description
  if body.status is not None:
    if body.status not in STATUS_LABELS:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的状态值")
    ticket.status = body.status
  if body.priority is not None:
    if body.priority not in PRIORITY_LABELS:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的优先级")
    ticket.priority = body.priority
  if body.assignee_id is not None:
    assignee = db.query(User).filter(
      User.id == body.assignee_id,
      User.company_id == current_user.company_id,
    ).first()
    if not assignee:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指派人不存在")
    ticket.assignee_id = body.assignee_id

  ticket.updated_at = datetime.utcnow()
  db.commit()
  db.refresh(ticket)
  return _build_ticket_out(ticket)


@router.delete("/{ticket_id}", summary="删除工单")
def delete_ticket(
  ticket_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """删除工单（仅 admin）"""
  if current_user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可删除工单")

  ticket = db.query(Ticket).filter(
    Ticket.id == ticket_id,
    Ticket.company_id == current_user.company_id,
  ).first()
  if not ticket:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")

  db.delete(ticket)
  db.commit()
  return {"message": "工单已删除", "id": ticket_id}
