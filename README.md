# 小云智服 XiaoYun — 服饰电商 AI 售后客服协同工作台

> 面向中小服饰电商的 AI 售后客服系统：懂退换货政策、能溯源回答、低置信度自动转人工。

## 项目背景

分析 8 份真实服饰电商客服对话后发现：中小店铺的平台机器人答非所问，人工回复慢且不专业，而服饰类目退换货率高达 20-30%，售后咨询量是其他类目的 3-5 倍。

## 核心功能

- **智能问答**：基于 RAG 的售后政策问答，支持多轮对话
- **来源溯源**：每个回答标注来自哪份政策文档
- **置信度评分**：低置信度回答自动标记，坐席确认后发送
- **知识库管理**：支持上传/管理售后政策、物流说明、FAQ
- **会话与工单**：对话历史、人工接管、工单流转
- **效果看板**：解决率、AI 采纳率、工单分布等核心指标

## 技术栈

- **前端**：React + Vite + Tailwind CSS
- **后端**：Python FastAPI + SQLAlchemy
- **数据库**：SQLite
- **AI**：智谱 GLM-4-Flash + FAISS 向量检索（RAG）
- **认证**：JWT

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
├── docs/              # 产品文档（定位/需求/竞品/Cursor开发PRD）
├── prototype/         # HTML 原型（25页）
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── core/      # 配置与安全
│   │   ├── models/    # 数据库模型
│   │   ├── schemas/   # Pydantic Schema
│   │   ├── routers/   # API 路由
│   │   ├── services/  # RAG / LLM / AI 建议
│   │   └── main.py
│   └── requirements.txt
└── frontend/          # React 前端
    └── src/
        ├── api/       # API 客户端
        ├── components/# 布局组件
        ├── context/   # 认证上下文
        └── pages/     # 页面
```

## 文档索引

| 文档 | 说明 |
|------|------|
| [产品定位](docs/00_产品定位.md) | 一句话定位、目标用户、产品边界、差异化 |
| [需求分析与用户研究](docs/01_需求分析与用户研究.md) | 痛点诊断、用户画像、KPI 体系 |
| [竞品分析与差异化定位](docs/02_竞品分析与差异化定位.md) | 竞品拆解、差异化支柱 |
| [Cursor开发文档PRD](docs/03_Cursor开发文档PRD.md) | 技术栈、数据表、API、开发计划 |

## 开发进度

- [x] 阶段0：产品定位
- [x] 阶段1：需求分析与用户研究
- [x] 阶段2：竞品分析
- [x] 阶段3：产品设计（PRD + 25页 HTML 原型）
- [x] 阶段4：技术实现（阶段 A-D 全部完成）
  - [x] 阶段A — 项目骨架（认证、布局、路由）
  - [x] 阶段B — 会话管理 + 知识库 RAG
  - [x] 阶段C — AI 回复建议 + 置信度评分
  - [x] 阶段D — 工单系统 + 数据统计
- [ ] 阶段5：评测与效果验证
- [ ] 阶段6：包装与求职

## 作品集说明

本项目为 AI 产品经理求职作品集，每份文档内嵌「面试话术」模块，覆盖端到端链路设计、评测方法、badcase 迭代等。
