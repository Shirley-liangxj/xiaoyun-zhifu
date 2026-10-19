"""AI 建议状态与采纳率统计。

`is_sent` 是历史兼容字段，不能再拿它直接当成“坐席采纳”。
新字段 suggestion_status 只对 ai_suggestion 生效：
pending / accepted / edited_and_accepted / rejected / auto_sent / legacy_sent。
"""

from collections.abc import Iterable

HUMAN_SUGGESTION_STATUSES = {"pending", "accepted", "edited_and_accepted", "rejected"}
PROCESSED_SUGGESTION_STATUSES = {"accepted", "edited_and_accepted", "rejected"}


def summarize_adoption(statuses: Iterable[str | None]) -> dict:
  values = list(statuses)
  human = [s for s in values if s in HUMAN_SUGGESTION_STATUSES]
  accepted = sum(s == "accepted" for s in human)
  edited_and_accepted = sum(s == "edited_and_accepted" for s in human)
  rejected = sum(s == "rejected" for s in human)
  pending = sum(s == "pending" for s in human)
  auto_sent = sum(s == "auto_sent" for s in values)
  processed = sum(s in PROCESSED_SUGGESTION_STATUSES for s in human)
  adopted = accepted + edited_and_accepted
  return {
    "human_suggestions": len(human),
    "processed_suggestions": processed,
    "accepted": accepted,
    "edited_and_accepted": edited_and_accepted,
    "rejected": rejected,
    "pending": pending,
    "auto_sent": auto_sent,
    "accept_rate": round(adopted / processed * 100, 1) if processed else 0.0,
  }
