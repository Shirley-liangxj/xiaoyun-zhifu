"""知识库检索工具 — 包装现有 RAG 检索，供模型自主调用

这是给 Agent 的「查资料」能力：当模型判断用户问的是政策/规则/流程类问题时，
主动调用本工具去知识库检索，而不是由外部代码写死「咨询类才走检索」。

设计说明：
- 复用现有 search_knowledge（FAISS 向量检索）+ _calc_confidence（相似度映射），
  不新增任何依赖、不复制一套检索逻辑。
- company_id 由调用方（agent_loop）透传，工具自身不猜测租户。
"""
from __future__ import annotations

from app.services.ai_suggestion import _calc_confidence
from app.services.rag import search_knowledge


def search_policy(
  message: str,
  query: str | None = None,
  company_id: int | None = None,
  top_k: int = 3,
) -> dict:
  """检索知识库，返回统一工具结构（ok/source/needs_human/result/summary）。"""
  q = (query or message or "").strip()
  if not q:
    return {
      "ok": False,
      "source": "rag",
      "needs_human": False,
      "result": {"sources": [], "confidence": 0.0},
      "summary": "检索词为空，无法查询知识库",
    }

  if company_id is None:
    return {
      "ok": False,
      "source": "rag",
      "needs_human": False,
      "result": {"sources": [], "confidence": 0.0},
      "summary": "缺少 company_id，无法确定要检索哪个租户的知识库",
    }

  try:
    sources = search_knowledge(company_id, q, top_k=top_k)
  except Exception as exc:  # 检索失败不应让整轮对话崩掉
    return {
      "ok": False,
      "source": "rag",
      "needs_human": False,
      "result": {"sources": [], "confidence": 0.0, "error": str(exc)},
      "summary": f"知识库检索失败：{exc}",
    }

  confidence = _calc_confidence(sources)

  if not sources:
    return {
      "ok": False,
      "source": "rag",
      "needs_human": False,
      "result": {"query": q, "sources": [], "confidence": confidence},
      "summary": "知识库未检索到相关资料，可考虑转人工或请用户换个问法",
    }

  brief = "；".join(f"《{s['title']}》(相似度{s['score']:.2f})" for s in sources)
  return {
    "ok": True,
    "source": "rag",
    "needs_human": False,
    "result": {
      "query": q,
      "confidence": confidence,
      "sources": [
        {
          "doc_id": s["doc_id"],
          "title": s["title"],
          "category": s["category"],
          "score": s["score"],
          "text": s["text"],
        }
        for s in sources
      ],
    },
    "summary": f"检索到 {len(sources)} 段相关资料：{brief}",
  }
