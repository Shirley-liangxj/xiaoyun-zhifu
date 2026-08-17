"""小云智服 - FastAPI 应用入口"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth, conversations, eval, knowledge, public_chat, quick_replies, settings, stats, tickets, users


@asynccontextmanager
async def lifespan(app: FastAPI):
  """应用生命周期：启动时建表"""
  Base.metadata.create_all(bind=engine)
  yield


app = FastAPI(
  title="小云智服 API",
  description="AI售后客服协同工作台 - 面向中小服饰电商",
  version="0.1.0",
  lifespan=lifespan,
)

# CORS 配置 - 支持生产环境域名（默认放开所有来源，可通过 CORS_ORIGINS 环境变量限制）
cors_origins = os.getenv("CORS_ORIGINS", "*")
if cors_origins == "*":
  app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
  )
else:
  app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(conversations.router)
app.include_router(tickets.router)
app.include_router(knowledge.router)
app.include_router(stats.router)
app.include_router(eval.router)
app.include_router(settings.router)
app.include_router(public_chat.router)
app.include_router(quick_replies.router)


@app.get("/", tags=["健康检查"])
def root():
  """根路径健康检查"""
  return {"message": "小云智服 API 运行中", "version": "0.1.0"}