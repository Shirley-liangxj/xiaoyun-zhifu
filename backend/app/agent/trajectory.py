"""会话轨迹 — 追加写入 jsonl，供 badcase 回放"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

TRACES_PATH = Path(__file__).resolve().parents[2] / "data" / "traces.jsonl"


def append_trace(record: dict) -> None:
  TRACES_PATH.parent.mkdir(parents=True, exist_ok=True)
  payload = {
    "ts": datetime.now(timezone.utc).isoformat(),
    **record,
  }
  with open(TRACES_PATH, "a", encoding="utf-8") as f:
    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
