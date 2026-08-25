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
