"""AI 建议状态与采纳率统计。

`is_sent` 是历史兼容字段，不能再拿它直接当成“坐席采纳”。
新字段 suggestion_status 只对 ai_suggestion 生效：
pending / accepted / edited_and_accepted / rejected / auto_sent / legacy_sent。

口径说明（对外必须一起说，否则会被误读）：
- accept_rate 分母只算“坐席已处理”的建议（采纳 + 编辑后采纳 + 拒绝）。
  auto_sent 是 AI 直接回复买家、未经坐席审核的自动应答，计入会把“自动应答量”
  混进“人工认可度”，因此单独统计、单独展示。
- 分母为 0 时返回 None（无定义）而不是 0.0 —— 0/0 不等于 0%，
  渲染成 0% 会被误读成“AI 建议全被否”。
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

  # AI 自动应答率 = 自动应答 ÷（自动应答 + 待人工处理）
  # 这才是商家关心的“AI 独立处理了多少”，与人工认可度互不替代。
  auto_denominator = auto_sent + pending
  auto_rate = round(auto_sent / auto_denominator * 100, 1) if auto_denominator else None

  return {
    "human_suggestions": len(human),
    "processed_suggestions": processed,
    "accepted": accepted,
    "edited_and_accepted": edited_and_accepted,
    "rejected": rejected,
    "pending": pending,
    "auto_sent": auto_sent,
    "total_suggestions": len(values),
    # 无分母时为 None，前端渲染「—」而不是 0%
    "accept_rate": round(adopted / processed * 100, 1) if processed else None,
    "auto_rate": auto_rate,
  }