"""轻量 SQLite 列迁移：create_all 不会改已有表"""
from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_sqlite_columns(engine: Engine) -> None:
  """为已有表补充缺失列（仅 SQLite）。"""
  if engine.dialect.name != "sqlite":
    return

  with engine.begin() as conn:
    cols = {
      row[1]
      for row in conn.execute(text("PRAGMA table_info(conversations)")).fetchall()
    }
    if "agent_last_read_at" not in cols:
      conn.execute(text("ALTER TABLE conversations ADD COLUMN agent_last_read_at DATETIME"))

    message_cols = {
      row[1]
      for row in conn.execute(text("PRAGMA table_info(messages)")).fetchall()
    }
    if "suggestion_status" not in message_cols:
      conn.execute(text("ALTER TABLE messages ADD COLUMN suggestion_status VARCHAR(20)"))
      # 旧数据无法可靠区分“买家自动回复”和“坐席采纳”，因此明确标为 legacy，
      # 统计时不把它们冒充为新的采纳事件。
      conn.execute(text(
        "UPDATE messages SET suggestion_status = "
        "CASE WHEN role = 'ai_suggestion' AND is_sent = 1 THEN 'legacy_sent' "
        "WHEN role = 'ai_suggestion' AND is_sent = 0 THEN 'pending' ELSE NULL END"
      ))

    review_cols = {
      row[1]
      for row in conn.execute(text("PRAGMA table_info(human_review_actions)")).fetchall()
    }
    review_columns = {
      "risk_reason": "TEXT DEFAULT ''",
      "buyer_confirmed_at": "DATETIME",
      "reviewer_id": "INTEGER",
      "reviewed_at": "DATETIME",
      "review_note": "TEXT DEFAULT ''",
      "resolved_at": "DATETIME",
    }
    for name, sql_type in review_columns.items():
      if name not in review_cols:
        conn.execute(text(f"ALTER TABLE human_review_actions ADD COLUMN {name} {sql_type}"))
    if review_cols:
      conn.execute(text(
        "UPDATE human_review_actions SET status = 'pending_buyer' WHERE status = 'pending'"
      ))

    gap_cols = {
      row[1]
      for row in conn.execute(text("PRAGMA table_info(knowledge_gaps)")).fetchall()
    }
    gap_columns = {
      "knowledge_doc_id": "INTEGER",
      "resolution_version": "INTEGER DEFAULT 0",
      "last_error": "TEXT",
      "resolved_at": "DATETIME",
    }
    for name, sql_type in gap_columns.items():
      if name not in gap_cols:
        conn.execute(text(f"ALTER TABLE knowledge_gaps ADD COLUMN {name} {sql_type}"))
