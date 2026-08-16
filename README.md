# 小云智服

AI售后客服协同工作台 — 面向中小服饰电商

## 技术栈

- **前端**: React + Vite + Tailwind CSS
- **后端**: Python FastAPI + SQLAlchemy
- **数据库**: SQLite
- **AI**: 智谱 GLM-4-Flash + FAISS（阶段B）
- **认证**: JWT

## 快速启动

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

API 文档：http://localhost:8000/docs

### 2. 前端

```bash
cd frontend
npm install
cp .env.example .env        # Windows: copy .env.example .env
npm run dev
```

访问：http://localhost:5173

## 项目结构

```
xiaoyun/
├── backend/
│   ├── app/
│   │   ├── core/          # 配置与安全
│   │   ├── models/        # 数据库模型
│   │   ├── schemas/       # Pydantic Schema
│   │   ├── routers/       # API 路由
│   │   ├── database.py    # 数据库连接
│   │   ├── deps.py        # 依赖注入
│   │   └── main.py        # 应用入口
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── api/           # API 客户端
    │   ├── components/    # 布局组件
    │   ├── context/       # 认证上下文
    │   └── pages/         # 页面
    ├── package.json
    └── .env.example
```

## 阶段进度

- [x] **阶段A** - 项目骨架（认证、布局、路由）
- [x] **阶段B** - 会话管理 + 知识库 RAG
- [x] **阶段C** - AI 回复建议 + 置信度评分
- [x] **阶段D** - 工单系统 + 数据统计
