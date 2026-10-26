"""买家端公开对话路由 - 无需登录（带 IP 频控）"""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.agent import confirm_pending_action, run_agent_turn
from app.core.config import settings
from app.database import get_db
from app.models import Company
from app.schemas.public import (
  PublicChatRequest,
  PublicChatResponse,
  PublicConfigOut,
  PublicConfirmRequest,
  PublicConversationOut,
  PublicOrderItemOut,
  PublicResolveRequest,
  PublicTransferRequest,
)
from app.services.errors import ExternalServiceError
from app.services.public_chat import (
  buyer_response,
  list_buyer_messages,
  list_buyer_orders,
  resolve_conversation,
  transfer_to_human,
)
from app.services.settings import get_or_create_settings

router = APIRouter(prefix="/api/public", tags=["买家端"])

# —— IP 频控：公开接口裸奔在公网上，没有这层任何人都能循环烧 LLM token ——
# 每 IP 每分钟最多 10 次会话类请求；窗口滚动清理，无需外部依赖（单进程演示规模够用）。
RATE_LIMIT = 10
RATE_WINDOW = 60
_rate_log: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
  # 优先取反代头；取不到就用直连地址
  fwd = request.headers.get("x-forwarded-for", "")
  return (fwd.split(",")[0].strip() if fwd else None) or (request.client.host if request.client else "unknown")


def rate_limit(request: Request) -> None:
  now = time.monotonic()
  q = _rate_log[_client_ip(request)]
  while q and now - q[0] > RATE_WINDOW:
    q.popleft()
  if len(q) >= RATE_LIMIT:
    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="请求太频繁，请稍后再试")
  q.append(now)


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


@router.post("/chat", response_model=PublicChatResponse, summary="买家端 AI 对话（含意图控制层）")
def public_chat(
  body: PublicChatRequest,
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
  _: None = Depends(rate_limit),
):
  cid = resolve_company_id(db, body.company_id if body.company_id is not None else company_id)
  try:
    result = run_agent_turn(
      db, cid, body.message, body.conversation_id, body.customer_name
    )
    return PublicChatResponse(**buyer_response(result))
  except ExternalServiceError as e:
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
  except Exception as e:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"对话失败: {e}")


@router.post("/confirm", response_model=PublicChatResponse, summary="确认高风险动作（HITL）")
def public_confirm(
  body: PublicConfirmRequest,
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
  _: None = Depends(rate_limit),
):
  cid = resolve_company_id(db, body.company_id if body.company_id is not None else company_id)
  try:
    result = confirm_pending_action(
      db, cid, body.confirmation_id, body.conversation_id, body.customer_name
    )
    return PublicChatResponse(**buyer_response(result))
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/transfer", response_model=PublicChatResponse, summary="买家主动转人工")
def public_transfer(
  body: PublicTransferRequest,
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
  _: None = Depends(rate_limit),
):
  cid = resolve_company_id(db, body.company_id if body.company_id is not None else company_id)
  result = transfer_to_human(db, cid, body.conversation_id, body.customer_name)
  return PublicChatResponse(**buyer_response(result))


@router.get("/conversations/{conversation_id}", response_model=PublicConversationOut, summary="买家拉取会话消息")
def public_messages(
  conversation_id: int,
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
):
  cid = resolve_company_id(db, company_id)
  return PublicConversationOut(**list_buyer_messages(db, cid, conversation_id))


@router.get("/orders", response_model=list[PublicOrderItemOut], summary="买家端「我的订单」列表")
def public_orders(
  customer_name: str = Query(default="访客", max_length=50),
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
):
  """演示环境的订单列表：按昵称匹配演示订单，卡片点击代替手输单号。"""
  resolve_company_id(db, company_id)
  return list_buyer_orders(company_id or settings.DEFAULT_COMPANY_ID, customer_name)


@router.post("/resolve", response_model=PublicChatResponse, summary="买家确认问题已解决，结束咨询")
def public_resolve(
  body: PublicResolveRequest,
  company_id: int | None = Query(None, description="租户公司 ID"),
  db: Session = Depends(get_db),
  _: None = Depends(rate_limit),
):
  cid = resolve_company_id(db, body.company_id if body.company_id is not None else company_id)
  try:
    result = resolve_conversation(db, cid, body.conversation_id, body.customer_name)
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
  return PublicChatResponse(**buyer_response(result))
