"""买家端公开对话路由 - 无需登录"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.schemas.public import PublicChatRequest, PublicChatResponse
from app.services.public_chat import chat_for_buyer

router = APIRouter(prefix="/api/public", tags=["买家端"])


@router.post("/chat", response_model=PublicChatResponse, summary="买家端 AI 对话")
def public_chat(body: PublicChatRequest, db: Session = Depends(get_db)):
  """
  买家端公开对话接口，无需登录。
  基于 RAG 检索知识库生成回答，低置信度时建议转人工。
  """
  company_id = settings.DEFAULT_COMPANY_ID
  try:
    result = chat_for_buyer(
      db, company_id, body.message, body.conversation_id, body.customer_name
    )
    return PublicChatResponse(**result)
  except Exception as e:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"对话失败: {e}")
