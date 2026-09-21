"""智谱 Embedding 服务 - 文本向量化"""
import time

import httpx

from app.core.config import settings
from app.services.errors import ExternalServiceError

# embed_text / embed_batch 共用：最多 3 次，间隔 1s、2s
_EMBED_MAX_ATTEMPTS = 3
_EMBED_RETRY_WAITS = (1, 2)


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
    """将单条文本转为向量（HTTP 重试在 embed_batch 内，签名与返回类型不变）"""
    return self.embed_batch([text])[0]

  def embed_batch(self, texts: list[str]) -> list[list[float]]:
    """批量文本向量化；网络失败最多重试 3 次（间隔 1s、2s），全部失败才抛出。"""
    self._check_api_key()
    last_http_err: Exception | None = None
    for attempt in range(_EMBED_MAX_ATTEMPTS):
      try:
        with httpx.Client(timeout=30) as client:
          resp = client.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
          )
          resp.raise_for_status()
          data = resp.json()
          items = sorted(data["data"], key=lambda x: x["index"])
          return [item["embedding"] for item in items]
      except httpx.HTTPError as e:
        last_http_err = e
        if attempt < _EMBED_MAX_ATTEMPTS - 1:
          time.sleep(_EMBED_RETRY_WAITS[attempt])
          continue
        raise ExternalServiceError(f"向量 API 请求失败: {e}") from e
      except (KeyError, IndexError, TypeError) as e:
        raise ExternalServiceError(f"向量 API 响应格式异常: {e}") from e
    # 理论上不可达；保留以防循环逻辑变更
    raise ExternalServiceError(f"向量 API 请求失败: {last_http_err}") from last_http_err


# 单例
embedding_service = EmbeddingService()
