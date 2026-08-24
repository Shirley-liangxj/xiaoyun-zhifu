"""买家端公开对话路由 - 无需登录"""
from fastapi import APIRouter, Depends, HTTPException, status
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
from app.services.public_chat import chat_for_buyer, list_buyer_messages, transfer_to_human
from app.services.errors import ExternalServiceError
from app.services.settings import get_or_create_settings

router = APIRouter(prefix="/api/public", tags=["买家端"])


def _company_id() -> int:
  return settings.DEFAULT_COMPANY_ID


@router.get("/config", response_model=PublicConfigOut, summary="买家端欢迎语")
def public_config(db: Session = Depends(get_db)):
  company_id = _company_id()
  company_settings = get_or_create_settings(db, company_id)
  company = db.query(Company).filter(Company.id == company_id).first()
  return PublicConfigOut(
    welcome_message=company_settings.welcome_message,
    company_name=company.name if company else "云裳服饰",
    confidence_threshold=company_settings.confidence_threshold,
  )


@router.post("/chat", response_model=PublicChatResponse, summary="买家端 AI 对话")
def public_chat(body: PublicChatRequest, db: Session = Depends(get_db)):
  try:
    result = chat_for_buyer(
      db, _company_id(), body.message, body.conversation_id, body.customer_name
    )
    return PublicChatResponse(**result)
  except ExternalServiceError as e:
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
  except Exception as e:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"对话失败: {e}")


@router.post("/transfer", response_model=PublicChatResponse, summary="买家主动转人工")
def public_transfer(body: PublicTransferRequest, db: Session = Depends(get_db)):
  result = transfer_to_human(db, _company_id(), body.conversation_id, body.customer_name)
  return PublicChatResponse(**result)


@router.get("/conversations/{conversation_id}", response_model=PublicConversationOut, summary="买家拉取会话消息")
def public_messages(conversation_id: int, db: Session = Depends(get_db)):
  return PublicConversationOut(**list_buyer_messages(db, _company_id(), conversation_id))
