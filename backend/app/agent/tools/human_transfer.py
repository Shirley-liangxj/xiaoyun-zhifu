"""转人工工具 — 模型「我处理不了」的出口，强制人工介入

硬约束（改造后仍必须保留）：
本工具永远返回 needs_human=True，且不执行任何业务动作。
无论模型接下来想说什么，agent_loop 看到这个标记后必须立即中断循环、
走人工确认/转接流程 —— 转人工的判断权在代码，不在模型。
"""
from __future__ import annotations

DEFAULT_REASON = "模型判定超出自动处理范围"


def transfer_to_human(message: str, reason: str | None = None) -> dict:
  """声明本次需要人工介入。不执行任何业务动作。"""
  r = (reason or DEFAULT_REASON).strip() or DEFAULT_REASON
  return {
    "ok": True,
    "source": "policy",
    "needs_human": True,
    "result": {
      "reason": r,
      "auto_execute": False,
      "demo": True,
    },
    "summary": f"已标记转人工，原因：{r}。未执行任何自动动作。",
  }
