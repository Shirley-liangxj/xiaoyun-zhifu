"""知识库路由 - 文档 CRUD + RAG 检索"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import KnowledgeDoc, KnowledgeGap, User
from app.schemas.knowledge import (
  KnowledgeDocCreate,
  KnowledgeDocOut,
  KnowledgeDocUpdate,
  KnowledgeSearchRequest,
  KnowledgeSearchResponse,
  KnowledgeSearchResult,
)
from app.schemas.knowledge_gap import KnowledgeGapOut, KnowledgeGapResolve
from app.services.rag import index_document, rebuild_company_index, remove_document_index, search_knowledge

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.get("/", response_model=list[KnowledgeDocOut], summary="获取知识库文档列表")
def list_docs(
  category: str | None = None,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """获取当前公司的知识库文档，可按分类筛选"""
  query = db.query(KnowledgeDoc).filter(KnowledgeDoc.company_id == current_user.company_id)
  if category:
    query = query.filter(KnowledgeDoc.category == category)
  return query.order_by(KnowledgeDoc.updated_at.desc()).all()


@router.post("/", response_model=KnowledgeDocOut, summary="创建知识库文档")
def create_doc(
  body: KnowledgeDocCreate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """创建文档并自动向量化索引"""
  doc = KnowledgeDoc(
    company_id=current_user.company_id,
    title=body.title,
    content=body.content,
    category=body.category,
  )
  db.add(doc)
  db.commit()
  db.refresh(doc)

  try:
    index_document(db, doc)
  except Exception:
    pass

  db.refresh(doc)
  return doc


@router.post("/search", response_model=KnowledgeSearchResponse, summary="RAG 知识检索")
def search_docs(
  body: KnowledgeSearchRequest,
  current_user: User = Depends(get_current_user),
):
  """基于 FAISS 向量检索相关知识块，返回来源溯源结果"""
  try:
    results = search_knowledge(current_user.company_id, body.query, body.top_k)
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
  except Exception as e:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检索失败: {e}")

  return KnowledgeSearchResponse(
    query=body.query,
    results=[KnowledgeSearchResult(**r) for r in results],
  )


@router.post("/reindex", summary="重建全部索引")
def reindex_all(
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """重建当前公司所有知识库文档的向量索引"""
  try:
    count = rebuild_company_index(db, current_user.company_id)
    return {"message": "索引重建完成", "indexed_count": count}
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{doc_id}", response_model=KnowledgeDocOut, summary="获取文档详情")
def get_doc(
  doc_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """获取单篇文档详情"""
  doc = db.query(KnowledgeDoc).filter(
    KnowledgeDoc.id == doc_id,
    KnowledgeDoc.company_id == current_user.company_id,
  ).first()
  if not doc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
  return doc


@router.put("/{doc_id}", response_model=KnowledgeDocOut, summary="更新文档")
def update_doc(
  doc_id: int,
  body: KnowledgeDocUpdate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """更新文档并重新向量化"""
  doc = db.query(KnowledgeDoc).filter(
    KnowledgeDoc.id == doc_id,
    KnowledgeDoc.company_id == current_user.company_id,
  ).first()
  if not doc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

  if body.title is not None:
    doc.title = body.title
  if body.content is not None:
    doc.content = body.content
  if body.category is not None:
    doc.category = body.category

  db.commit()
  db.refresh(doc)

  try:
    index_document(db, doc)
  except Exception:
    pass

  db.refresh(doc)
  return doc


@router.delete("/{doc_id}", summary="删除文档")
def delete_doc(
  doc_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """删除文档及其向量索引"""
  doc = db.query(KnowledgeDoc).filter(
    KnowledgeDoc.id == doc_id,
    KnowledgeDoc.company_id == current_user.company_id,
  ).first()
  if not doc:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

  remove_document_index(current_user.company_id, doc_id)
  db.delete(doc)
  db.commit()
  return {"message": "文档已删除", "id": doc_id}


@router.get("/gaps", response_model=list[KnowledgeGapOut], summary="获取知识缺口列表")
def list_gaps(
  status_filter: str | None = None,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """获取未命中或低置信度的问题列表"""
  query = db.query(KnowledgeGap).filter(KnowledgeGap.company_id == current_user.company_id)
  if status_filter:
    query = query.filter(KnowledgeGap.status == status_filter)
  return query.order_by(KnowledgeGap.hit_count.desc()).all()


@router.post("/gaps/{gap_id}/resolve", response_model=KnowledgeGapOut, summary="解决知识缺口")
def resolve_gap(
  gap_id: int,
  body: KnowledgeGapResolve,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """标记知识缺口已解决，并记录补充答案"""
  gap = db.query(KnowledgeGap).filter(
    KnowledgeGap.id == gap_id,
    KnowledgeGap.company_id == current_user.company_id,
  ).first()
  if not gap:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识缺口不存在")

  gap.status = "resolved"
  gap.suggested_answer = body.suggested_answer
  db.commit()
  db.refresh(gap)
  return gap


@router.post("/gaps/{gap_id}/ignore", summary="忽略知识缺口")
def ignore_gap(
  gap_id: int,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """忽略该知识缺口"""
  gap = db.query(KnowledgeGap).filter(
    KnowledgeGap.id == gap_id,
    KnowledgeGap.company_id == current_user.company_id,
  ).first()
  if not gap:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识缺口不存在")

  gap.status = "ignored"
  db.commit()
  return {"message": "已忽略", "id": gap_id}
