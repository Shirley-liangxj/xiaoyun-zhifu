"""数据库连接与会话管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# SQLite 需要 check_same_thread=False
engine = create_engine(
  settings.DATABASE_URL,
  connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
  """SQLAlchemy 声明基类"""
  pass


def get_db():
  """依赖注入：获取数据库会话，请求结束后自动关闭"""
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()
