"""智谱 GLM 大模型服务 - 文本生成"""
import httpx

from app.core.config import settings


class LLMService:
  """调用智谱 GLM-4-Flash API 生成回复"""

  def __init__(self):
    self.api_key = settings.LLM_API_KEY
    self.base_url = settings.LLM_BASE_URL
    self.model = settings.LLM_MODEL

  def _check_api_key(self):
    if not self.api_key or self.api_key == "your_zhipu_api_key_here":
      raise ValueError("未配置 LLM_API_KEY，请在 .env 中设置智谱 API 密钥")

  def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
    """
    调用对话补全 API。
    messages 格式: [{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    self._check_api_key()
    with httpx.Client(timeout=60) as client:
      resp = client.post(
        f"{self.base_url}/chat/completions",
        headers={"Authorization": f"Bearer {self.api_key}"},
        json={
          "model": self.model,
          "messages": messages,
          "temperature": temperature,
        },
      )
      resp.raise_for_status()
      data = resp.json()
      return data["choices"][0]["message"]["content"]


# 单例
llm_service = LLMService()
