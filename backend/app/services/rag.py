"""RAG 编排服务 - 文档分块、索引、检索"""
import re

from sqlalchemy.orm import Session

from app.models import KnowledgeDoc
from app.services.embedding import embedding_service
from app.services.vector_store import get_vector_store

# 分块参数
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50


def split_text(text: str) -> list[str]:
  """将文档内容切分为重叠文本块"""
  paragraphs = re.split(r"\n{2,}", text.strip())
  chunks: list[str] = []
  current = ""

  for para in paragraphs:
    para = para.strip()
    if not para:
      continue
    if len(current) + len(para) + 1 <= CHUNK_SIZE:
      current = f"{current}\n{para}".strip() if current else para
    else:
      if current:
        chunks.append(current)
      if len(para) > CHUNK_SIZE:
        for i in range(0, len(para), CHUNK_SIZE - CHUNK_OVERLAP):
          chunks.append(para[i : i + CHUNK_SIZE])
        current = ""
      else:
        current = para

  if current:
    chunks.append(current)

  return chunks if chunks else [text[:CHUNK_SIZE]]


def index_document(db: Session, doc: KnowledgeDoc) -> bool:
  """对单篇文档向量化并写入 FAISS（先移除旧块再添加新块）"""
  store = get_vector_store(doc.company_id)
  store.remove_doc_vectors(doc.id)

  chunks = split_text(doc.content)
  if not chunks:
    doc.is_indexed = False
    db.commit()
    return False

  try:
    embeddings = embedding_service.embed_batch(chunks)
    store.add_chunks(doc.id, doc.title, doc.category, chunks, embeddings)
    doc.is_indexed = True
    db.commit()
    return True
  except ValueError:
    doc.is_indexed = False
    db.commit()
    return False


def rebuild_company_index(db: Session, company_id: int) -> int:
  """重建公司全部知识库索引，返回成功索引的文档数"""
  store = get_vector_store(company_id)
  store.clear()

  docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.company_id == company_id).all()
  indexed_count = 0

  for doc in docs:
    chunks = split_text(doc.content)
    if not chunks:
      doc.is_indexed = False
      continue
    try:
      embeddings = embedding_service.embed_batch(chunks)
      store.add_chunks(doc.id, doc.title, doc.category, chunks, embeddings)
      doc.is_indexed = True
      indexed_count += 1
    except ValueError:
      doc.is_indexed = False

  db.commit()
  return indexed_count


def remove_document_index(company_id: int, doc_id: int):
  """从索引中移除文档向量块"""
  store = get_vector_store(company_id)
  store.remove_doc_vectors(doc_id)


def search_knowledge(company_id: int, query: str, top_k: int = 5) -> list[dict]:
  """RAG 检索：查询向量化后在 FAISS 中搜索 top_k 相关块"""
  query_embedding = embedding_service.embed_text(query)
  store = get_vector_store(company_id)
  return store.search(query_embedding, top_k=top_k)
