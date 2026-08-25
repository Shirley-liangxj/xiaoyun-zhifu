"""买家端公开对话路由 - 无需登录"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models import Company
from app.schemas.public import (
  PublicChatRequest,
  PublicChatResponse,
  PublicConfigOut,
  PublicConversationOut,
  PublicTransferRequest,
)
from app.services.errors import ExternalServiceError
from app.services.public_chat import chat_for_buyer, list_buyer_messages, transfer_to_human
from app.services.settings import get_or_create_settings

router = APIRouter(prefix="/api/public", tags=["买家端"])


def resolve_company_id(db: Session, company_id: int | None) -> int:
  """解析租户：显式 company_id 优先，否则回退默认公司。"""
  cid = company_id if company_id is not None else settings.DEFAULT_COMPANY_ID
  company = db.query(Company).filter(Company.id == cid).first()
  if not company:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="企业不存在")
  return cid


@router.get("/config", response_model=PublicConfigOut, summary="买家端欢迎语")
def public_config(
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
):
  cid = resolve_company_id(db, company_id)
  company_settings = get_or_create_settings(db, cid)
  company = db.query(Company).filter(Company.id == cid).first()
  return PublicConfigOut(
    welcome_message=company_settings.welcome_message,
    company_name=company.name if company else "智能客服",
    company_id=cid,
    confidence_threshold=company_settings.confidence_threshold,
  )


@router.post("/chat", response_model=PublicChatResponse, summary="买家端 AI 对话")
def public_chat(
  body: PublicChatRequest,
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
):
  cid = resolve_company_id(db, body.company_id if body.company_id is not None else company_id)
  try:
    result = chat_for_buyer(
      db, cid, body.message, body.conversation_id, body.customer_name
    )
    return PublicChatResponse(**result)
  except ExternalServiceError as e:
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
  except Exception as e:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"对话失败: {e}")


@router.post("/transfer", response_model=PublicChatResponse, summary="买家主动转人工")
def public_transfer(
  body: PublicTransferRequest,
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
):
  cid = resolve_company_id(db, body.company_id if body.company_id is not None else company_id)
  result = transfer_to_human(db, cid, body.conversation_id, body.customer_name)
  return PublicChatResponse(**result)


@router.get("/conversations/{conversation_id}", response_model=PublicConversationOut, summary="买家拉取会话消息")
def public_messages(
  conversation_id: int,
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
):
  cid = resolve_company_id(db, company_id)
  return PublicConversationOut(**list_buyer_messages(db, cid, conversation_id))
