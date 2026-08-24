"""系统设置路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import KnowledgeDoc, User
from app.schemas.settings import CompanyInfoUpdate, SettingsOut, SettingsUpdate, SystemStatusOut
from app.services.bootstrap import reset_demo_data_for_company
from app.services.embedding import embedding_service
from app.services.errors import ExternalServiceError
from app.services.rag import rebuild_company_index
from app.services.settings import get_or_create_settings

router = APIRouter(prefix="/api/settings", tags=["系统设置"])


@router.get("/", response_model=SettingsOut, summary="获取机器人设置")
def get_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
  return get_or_create_settings(db, current_user.company_id)


@router.put("/", response_model=SettingsOut, summary="更新机器人设置")
def update_settings(
  body: SettingsUpdate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  s = get_or_create_settings(db, current_user.company_id)
  if body.welcome_message is not None:
    s.welcome_message = body.welcome_message
  if body.confidence_threshold is not None:
    s.confidence_threshold = body.confidence_threshold
  if body.auto_suggest is not None:
    s.auto_suggest = body.auto_suggest
  if body.reject_message is not None:
    s.reject_message = body.reject_message
  db.commit()
  db.refresh(s)
  return s


@router.get("/status", response_model=SystemStatusOut, summary="系统状态")
def get_system_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
  """API Key 状态、模型信息、知识库索引状态"""
  key = app_settings.LLM_API_KEY or ""
  configured = bool(key and key != "your_zhipu_api_key_here")
  masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else ("已配置" if configured else "未配置")

  cid = current_user.company_id
  total = db.query(func.count(KnowledgeDoc.id)).filter(KnowledgeDoc.company_id == cid).scalar() or 0
  indexed = db.query(func.count(KnowledgeDoc.id)).filter(
    KnowledgeDoc.company_id == cid, KnowledgeDoc.is_indexed == True
  ).scalar() or 0

  return SystemStatusOut(
    api_key_configured=configured,
    api_key_masked=masked,
    llm_model=app_settings.LLM_MODEL,
    embedding_model=app_settings.EMBEDDING_MODEL,
    knowledge_docs_total=total,
    knowledge_docs_indexed=indexed,
    index_ready=indexed > 0,
    company_name=current_user.company.name if current_user.company else "",
  )


@router.post("/test-api", summary="测试 API 连接")
def test_api(current_user: User = Depends(get_current_user)):
  """测试智谱 API 是否可用"""
  try:
    embedding_service.embed_text("测试连接")
    return {"status": "ok", "message": "API 连接正常"}
  except (ValueError, ExternalServiceError) as e:
    return {"status": "error", "message": str(e)}
  except Exception as e:
    return {"status": "error", "message": f"连接失败: {e}"}


@router.post("/reindex", summary="重建知识库索引")
def reindex(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
  try:
    count = rebuild_company_index(db, current_user.company_id)
    return {"message": "索引重建完成", "indexed_count": count}
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
  except ExternalServiceError as e:
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.put("/company", summary="更新企业信息")
def update_company(
  body: CompanyInfoUpdate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  company = current_user.company
  if not company:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="企业信息不存在")
  company.name = body.company_name
  db.commit()
  return {"message": "企业信息已更新", "company_name": company.name}


@router.post("/reset-demo", summary="加载演示数据（管理员）")
def reset_demo(
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """重建当前租户的演示知识库、会话、工单（覆盖已有演示数据）。"""
  if current_user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可操作")
  reset_demo_data_for_company(db, current_user.company_id, current_user.id)
  return {"message": "演示数据已加载", "company_id": current_user.company_id}
