"""智谱 GLM 大模型服务 - 文本生成 + function calling"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from app.core.config import settings
from app.services.errors import ExternalServiceError


@dataclass
class LLMResult:
  """complete() 的完整返回：内容 + 工具调用 + token用量 + 耗时"""
  content: str
  tool_calls: list[dict] = field(default_factory=list)
  usage: dict = field(default_factory=dict)  # {"prompt_tokens","completion_tokens","total_tokens"}
  latency_ms: float = 0.0
  finish_reason: str | None = None
  raw: dict | None = None


class LLMService:
  """调用智谱 GLM-4-Flash API 生成回复"""

  def __init__(self):
    self.api_key = settings.LLM_API_KEY
    self.base_url = settings.LLM_BASE_URL
    self.model = settings.LLM_MODEL

  def _check_api_key(self):
    if not self.api_key or self.api_key == "your_zhipu_api_key_here":
      raise ValueError("未配置 LLM_API_KEY，请在 .env 中设置智谱 API 密钥")

  def complete(
    self,
    messages: list[dict],
    temperature: float = 0.7,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
  ) -> LLMResult:
    """
    调用对话补全 API，返回完整结果（含 tool_calls / usage / 耗时）。
    messages 格式: [{"role": "system"|"user"|"assistant"|"tool", "content": "...", ...}]
    tools 格式（可选）: [{"type":"function","function":{"name","description","parameters"}}]
    """
    self._check_api_key()
    payload = {
      "model": self.model,
      "messages": messages,
      "temperature": temperature,
    }
    if tools:
      payload["tools"] = tools
      if tool_choice is not None:
        payload["tool_choice"] = tool_choice

    start = time.perf_counter()
    try:
      with httpx.Client(timeout=60) as client:
        resp = client.post(
          f"{self.base_url}/chat/completions",
          headers={"Authorization": f"Bearer {self.api_key}"},
          json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        latency_ms = (time.perf_counter() - start) * 1000
        choice = data["choices"][0]
        msg = choice["message"]
        return LLMResult(
          content=msg.get("content") or "",
          tool_calls=msg.get("tool_calls") or [],
          usage=data.get("usage") or {},
          latency_ms=round(latency_ms, 1),
          finish_reason=choice.get("finish_reason"),
          raw=data,
        )
    except httpx.HTTPError as e:
      raise ExternalServiceError(f"大模型 API 请求失败: {e}") from e
    except (KeyError, IndexError, TypeError) as e:
      raise ExternalServiceError(f"大模型 API 响应格式异常: {e}") from e

  def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
    """
    调用对话补全 API，只取文本内容（保持旧签名，兼容现有调用方）。
    messages 格式: [{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    return self.complete(messages, temperature=temperature).content


# 单例
llm_service = LLMService()
