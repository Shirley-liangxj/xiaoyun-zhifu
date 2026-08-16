"""快捷话术路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import QuickReply, User
from app.schemas.quick_reply import QuickReplyCreate, QuickReplyOut, QuickReplyUpdate

router = APIRouter(prefix="/api/quick-replies", tags=["快捷话术"])


@router.get("/", response_model=list[QuickReplyOut], summary="获取话术列表")
def list_replies(
  category: str | None = None,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  query = db.query(QuickReply).filter(QuickReply.company_id == current_user.company_id)
  if category:
    query = query.filter(QuickReply.category == category)
  return query.order_by(QuickReply.use_count.desc()).all()


@router.post("/", response_model=QuickReplyOut, summary="新增话术")
def create_reply(
  body: QuickReplyCreate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  reply = QuickReply(company_id=current_user.company_id, **body.model_dump())
  db.add(reply)
  db.commit()
  db.refresh(reply)
  return reply


@router.put("/{reply_id}", response_model=QuickReplyOut, summary="更新话术")
def update_reply(
  reply_id: int,
  body: QuickReplyUpdate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  reply = db.query(QuickReply).filter(
    QuickReply.id == reply_id, QuickReply.company_id == current_user.company_id
  ).first()
  if not reply:
    raise HTTPException(status_code=404, detail="话术不存在")
  for k, v in body.model_dump(exclude_unset=True).items():
    setattr(reply, k, v)
  db.commit()
  db.refresh(reply)
  return reply


@router.delete("/{reply_id}", summary="删除话术")
def delete_reply(
  reply_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  reply = db.query(QuickReply).filter(
    QuickReply.id == reply_id, QuickReply.company_id == current_user.company_id
  ).first()
  if not reply:
    raise HTTPException(status_code=404, detail="话术不存在")
  db.delete(reply)
  db.commit()
  return {"message": "已删除", "id": reply_id}


@router.post("/{reply_id}/use", response_model=QuickReplyOut, summary="记录话术使用")
def use_reply(
  reply_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  reply = db.query(QuickReply).filter(
    QuickReply.id == reply_id, QuickReply.company_id == current_user.company_id
  ).first()
  if not reply:
    raise HTTPException(status_code=404, detail="话术不存在")
  reply.use_count += 1
  db.commit()
  db.refresh(reply)
  return reply
