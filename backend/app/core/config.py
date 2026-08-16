"""应用配置模块 - 从环境变量读取配置"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
  """全局配置类"""

  # 数据库
  DATABASE_URL: str = "sqlite:///./xiaoyun.db"

  # JWT 认证
  JWT_SECRET: str = "change-this-secret"
  JWT_ALGORITHM: str = "HS256"
  JWT_EXPIRE_MINUTES: int = 1440  # 24小时

  # 智谱 AI
  LLM_API_KEY: str = ""
  LLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
  EMBEDDING_MODEL: str = "embedding-3"
  EMBEDDING_DIM: int = 2048
  LLM_MODEL: str = "glm-4-flash"

  # 买家端默认租户
  DEFAULT_COMPANY_ID: int = 1

  # FAISS 索引存储目录
  FAISS_DATA_DIR: str = "./data/faiss"

  class Config:
    env_file = ".env"
    case_sensitive = True


settings = Settings()
