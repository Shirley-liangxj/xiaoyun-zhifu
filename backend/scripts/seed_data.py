"""数据初始化脚本 - 知识库、会话、工单、话术"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.database import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.services.bootstrap import reset_demo_data


def main():
  print("=== 小云智服数据初始化 ===")
  Base.metadata.create_all(bind=engine)

  if os.path.exists(settings.FAISS_DATA_DIR):
    shutil.rmtree(settings.FAISS_DATA_DIR)

  db = SessionLocal()
  try:
    reset_demo_data(db)
    print("  知识库 / 话术 / 会话 / 工单已重建")
    print("=== 初始化完成 ===")
    print("  账号: testadmin （密码见环境变量 XIAOYUN_DEMO_PASSWORD，默认 123456）")
    print("  工作台: http://localhost:5173/login")
    print("  买家端: http://localhost:5173/chat")
  finally:
    db.close()


if __name__ == "__main__":
  main()
