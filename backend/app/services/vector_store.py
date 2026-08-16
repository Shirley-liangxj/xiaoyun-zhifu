"""FAISS 向量存储 - 按公司隔离索引"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Optional

import faiss
import numpy as np

from app.core.config import settings


@dataclass
class ChunkMeta:
  """向量块元数据"""
  doc_id: int
  title: str
  category: str
  chunk_index: int
  text: str
  vector_idx: int  # 在 FAISS 索引中的位置


class VectorStore:
  """按公司维护独立的 FAISS 索引"""

  def __init__(self, company_id: int):
    self.company_id = company_id
    self.dim = settings.EMBEDDING_DIM
    os.makedirs(settings.FAISS_DATA_DIR, exist_ok=True)
    self.index_path = os.path.join(settings.FAISS_DATA_DIR, f"company_{company_id}.index")
    self.meta_path = os.path.join(settings.FAISS_DATA_DIR, f"company_{company_id}.meta.json")
    self.index: Optional[faiss.IndexFlatIP] = None
    self.metadata: list[ChunkMeta] = []
    self._load()

  def _load(self):
    """从磁盘加载索引和元数据"""
    if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
      self.index = faiss.read_index(self.index_path)
      with open(self.meta_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
        self.metadata = [ChunkMeta(**item) for item in raw]
    else:
      self.index = faiss.IndexFlatIP(self.dim)
      self.metadata = []

  def _save(self):
    """持久化索引和元数据到磁盘"""
    faiss.write_index(self.index, self.index_path)
    with open(self.meta_path, "w", encoding="utf-8") as f:
      json.dump([asdict(m) for m in self.metadata], f, ensure_ascii=False, indent=2)

  def _normalize(self, vectors: np.ndarray) -> np.ndarray:
    """L2 归一化，使内积等价于余弦相似度"""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vectors / norms

  def clear(self):
    """清空索引"""
    self.index = faiss.IndexFlatIP(self.dim)
    self.metadata = []
    self._save()

  def add_chunks(self, doc_id: int, title: str, category: str, chunks: list[str], embeddings: list[list[float]]):
    """添加文档的分块向量"""
    if not chunks:
      return
    vectors = np.array(embeddings, dtype=np.float32)
    vectors = self._normalize(vectors)
    start_idx = self.index.ntotal
    self.index.add(vectors)
    for i, text in enumerate(chunks):
      self.metadata.append(ChunkMeta(
        doc_id=doc_id, title=title, category=category,
        chunk_index=i, text=text, vector_idx=start_idx + i,
      ))
    self._save()

  def remove_doc_vectors(self, doc_id: int):
    """移除某文档的所有向量块（FAISS 不支持删除，重建索引）"""
    remaining = [m for m in self.metadata if m.doc_id != doc_id]
    if len(remaining) == len(self.metadata):
      return

    # 收集需要保留的向量
    if not remaining:
      self.clear()
      return

    # 重建：读取旧索引中保留的向量
    old_index = self.index
    keep_indices = [m.vector_idx for m in remaining]
    old_vectors = np.vstack([old_index.reconstruct(i) for i in keep_indices])

    self.index = faiss.IndexFlatIP(self.dim)
    self.index.add(old_vectors)

    # 更新元数据中的 vector_idx
    new_meta = []
    for i, m in enumerate(remaining):
      new_meta.append(ChunkMeta(
        doc_id=m.doc_id, title=m.title, category=m.category,
        chunk_index=m.chunk_index, text=m.text, vector_idx=i,
      ))
    self.metadata = new_meta
    self._save()

  def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """检索最相似的 top_k 个块"""
    if self.index.ntotal == 0:
      return []
    query = np.array([query_embedding], dtype=np.float32)
    query = self._normalize(query)
    k = min(top_k, self.index.ntotal)
    scores, indices = self.index.search(query, k)

    # 建立 vector_idx -> meta 的映射
    idx_map = {m.vector_idx: m for m in self.metadata}
    results = []
    for score, idx in zip(scores[0], indices[0]):
      if idx < 0 or idx not in idx_map:
        continue
      meta = idx_map[idx]
      results.append({
        "doc_id": meta.doc_id,
        "title": meta.title,
        "category": meta.category,
        "chunk_index": meta.chunk_index,
        "text": meta.text,
        "score": float(score),
      })
    return results


# 缓存各公司的 VectorStore 实例
_store_cache: dict[int, VectorStore] = {}


def get_vector_store(company_id: int) -> VectorStore:
  """获取（或创建）公司对应的向量存储实例"""
  if company_id not in _store_cache:
    _store_cache[company_id] = VectorStore(company_id)
  return _store_cache[company_id]
