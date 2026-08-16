"""智谱 Embedding 服务 - 文本向量化"""
import httpx

from app.core.config import settings


class EmbeddingService:
  """调用智谱 embedding-2 API 将文本转为向量"""

  def __init__(self):
    self.api_key = settings.LLM_API_KEY
    self.base_url = settings.LLM_BASE_URL
    self.model = settings.EMBEDDING_MODEL

  def _check_api_key(self):
    if not self.api_key or self.api_key == "your_zhipu_api_key_here":
      raise ValueError("未配置 LLM_API_KEY，请在 .env 中设置智谱 API 密钥")

  def embed_text(self, text: str) -> list[float]:
    """将单条文本转为向量"""
    return self.embed_batch([text])[0]

  def embed_batch(self, texts: list[str]) -> list[list[float]]:
    """批量文本向量化"""
    self._check_api_key()
    with httpx.Client(timeout=30) as client:
      resp = client.post(
        f"{self.base_url}/embeddings",
        headers={"Authorization": f"Bearer {self.api_key}"},
        json={"model": self.model, "input": texts},
      )
      resp.raise_for_status()
      data = resp.json()
      # 按 index 排序确保顺序一致
      items = sorted(data["data"], key=lambda x: x["index"])
      return [item["embedding"] for item in items]


# 单例
embedding_service = EmbeddingService()
