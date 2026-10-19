# 小云智服 — Cursor开发文档（PRD for Cursor）

> 版本：v1.2 | 日期：2026-09-16
> v1.1 更新：① 置信度阈值由 0.5 校准为 0.6（评测驱动）② 补充 v1.0 之后落地的多租户/评测/坐席协同接口 ③ 新增"已实现功能迭代记录"
> v1.2 更新：第十二节补 67 题结构与 0.6 校准方法；第十三节补多租户隔离 / LLM 降级 / MVP DoD。规划页 vs 真实页对照见 docs/功能全景-给协作方.md
> 用途：本文档是给AI编码工具（Cursor）的精确开发指令，包含技术栈、数据模型、API、业务流程、文件结构、开发计划和输出规范。
> 配套文档：docs/00_产品定位.md、docs/01_需求分析与用户研究.md、docs/02_竞品分析与差异化定位.md

---

## 一、项目概述

**产品名：** 小云智服 XiaoYun
**定位：** 面向中小服饰电商的售后客服：**AI 自主答 + 低置信转人工兜底**；转人工后坐席掌握发送权。
**定价（作品集假设，单一价）：** ¥299/月
**核心功能：** RAG知识库问答 + 来源溯源 + 置信度评分转人工 + 会话管理 + 效果看板
**目标：** 一个可部署上线的B端SaaS Demo，面试官可登录操作

---

## 二、技术栈

| 层 | 技术选型 | 版本要求 | 选择理由 |
|----|---------|---------|---------|
| 前端 | React + Vite + Tailwind CSS | React 18+ | 组件化，生态成熟，与原型HTML对应 |
| UI组件 | shadcn/ui 或 手写组件 | — | 轻量，可定制，匹配青绿视觉规范 |
| 后端 | Python FastAPI | Python 3.10+ | 异步高性能，自动生成API文档，AI项目首选 |
| 数据库 | SQLite + SQLAlchemy | — | 零配置，Demo够用，可后续迁移PostgreSQL |
| AI-向量检索 | FAISS + sentence-transformers | — | 本地运行，免费，支持语义检索 |
| AI-大模型 | 智谱GLM-4-Flash API（或DeepSeek） | — | 免费额度，中文好，响应快 |
| 文档解析 | PyPDF2 + python-docx | — | 支持PDF/TXT/DOCX上传 |
| 认证 | JWT（简单实现） | — | 无状态，前后端分离友好 |
| 部署 | 云服务器（Docker或直接运行） | — | 参考姐姐的部署方式，单IP+端口访问 |

---

## 三、数据模型（数据库表结构）

### 3.1 users（用户表 - 商家账号）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, autoincrement | 用户ID |
| email | VARCHAR(255) | UNIQUE, NOT NULL | 登录邮箱 |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希（bcrypt） |
| company_name | VARCHAR(100) | — | 公司/店铺名称 |
| role | VARCHAR(20) | DEFAULT 'admin' | 角色：admin/agent |
| avatar | VARCHAR(255) | — | 头像URL（可选） |
| created_at | DATETIME | DEFAULT now | 创建时间 |

### 3.2 sessions（会话表 - 买家与AI的对话）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(36) | PK | 会话ID（UUID） |
| user_id | INTEGER | FK→users.id | 所属商家 |
| buyer_name | VARCHAR(50) | DEFAULT '匿名买家' | 买家昵称 |
| status | VARCHAR(20) | DEFAULT 'active' | active/transferred/closed |
| satisfaction | INTEGER | NULL | 满意度1-5（会话结束时评价） |
| first_message_at | DATETIME | DEFAULT now | 首条消息时间 |
| last_message_at | DATETIME | — | 最后消息时间 |
| transferred_to_human | BOOLEAN | DEFAULT false | 是否转人工 |
| transfer_reason | VARCHAR(100) | NULL | 转人工原因 |

### 3.3 messages（消息表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, autoincrement | 消息ID |
| session_id | VARCHAR(36) | FK→sessions.id | 所属会话 |
| role | VARCHAR(20) | NOT NULL | user/assistant/system |
| content | TEXT | NOT NULL | 消息内容 |
| sources | TEXT | NULL | 来源溯源（JSON数组，存文档名+片段） |
| confidence | FLOAT | NULL | 置信度0-1（AI回复时） |
| need_human | BOOLEAN | DEFAULT false | 是否建议转人工 |
| feedback | VARCHAR(20) | NULL | positive/negative（用户点赞点踩） |
| created_at | DATETIME | DEFAULT now | 消息时间 |

### 3.4 documents（知识库文档表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, autoincrement | 文档ID |
| user_id | INTEGER | FK→users.id | 所属商家 |
| name | VARCHAR(255) | NOT NULL | 文档名称 |
| file_type | VARCHAR(20) | NOT NULL | pdf/txt/docx |
| file_size | INTEGER | — | 文件大小（字节） |
| chunk_count | INTEGER | DEFAULT 0 | 切分后的块数 |
| status | VARCHAR(20) | DEFAULT 'processing' | processing/ready/failed |
| category | VARCHAR(50) | DEFAULT '通用' | 分类：退换货/物流/FAQ/话术 |
| created_at | DATETIME | DEFAULT now | 上传时间 |

### 3.5 feedback（用户反馈表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, autoincrement | 反馈ID |
| session_id | VARCHAR(36) | FK→sessions.id | 所属会话 |
| message_id | INTEGER | FK→messages.id | 所属消息 |
| feedback_type | VARCHAR(20) | NOT NULL | positive/negative |
| comment | TEXT | NULL | 补充说明 |
| created_at | DATETIME | DEFAULT now | 反馈时间 |

### 3.6 knowledge_gaps（知识缺口表 - 未命中问题）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, autoincrement | ID |
| user_id | INTEGER | FK→users.id | 所属商家 |
| question | TEXT | NOT NULL | 用户问的问题 |
| hit_count | INTEGER | DEFAULT 1 | 被问次数 |
| status | VARCHAR(20) | DEFAULT 'pending' | pending/resolved/ignored |
| suggested_answer | TEXT | NULL | 建议补充的答案 |
| created_at | DATETIME | DEFAULT now | 首次出现时间 |
| last_seen_at | DATETIME | DEFAULT now | 最近出现时间 |

---

## 四、API接口设计

### 4.1 认证接口

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | /api/auth/register | 注册 | {email, password, company_name} | {token, user} |
| POST | /api/auth/login | 登录 | {email, password} | {token, user} |
| GET | /api/auth/me | 获取当前用户 | Header: Authorization | {user} |

### 4.2 对话接口

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | /api/chat | 发送消息（AI问答） | {session_id?, message} | {session_id, reply, sources, confidence, need_human} |
| GET | /api/sessions | 获取会话列表 | Query: page, status | {sessions[], total} |
| GET | /api/sessions/{id} | 获取会话详情 | — | {session, messages[]} |
| POST | /api/sessions/{id}/transfer | 转人工 | {reason} | {status: 'transferred'} |
| POST | /api/sessions/{id}/close | 关闭会话 | {satisfaction?} | {status: 'closed'} |
| POST | /api/messages/{id}/feedback | 消息反馈 | {feedback_type} | {status: 'ok'} |

### 4.3 知识库接口

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | /api/knowledge | 文档列表 | Query: category, page | {documents[], total} |
| POST | /api/knowledge/upload | 上传文档 | multipart/form-data (file, category) | {document_id, status} |
| DELETE | /api/knowledge/{id} | 删除文档 | — | {status: 'deleted'} |
| POST | /api/knowledge/{id}/reindex | 重建索引 | — | {status: 'processing'} |
| GET | /api/knowledge/gaps | 知识缺口列表 | Query: status, page | {gaps[], total} |
| POST | /api/knowledge/gaps/{id}/resolve | 标记已解决 | {suggested_answer} | {status: 'resolved'} |

### 4.4 看板/统计接口

| 方法 | 路径 | 说明 | 响应 |
|------|------|------|------|
| GET | /api/dashboard/stats | 核心指标 | {total_sessions, fcr, avg_response_time, transfer_rate, satisfaction} |
| GET | /api/dashboard/trends | 趋势数据 | Query: days (7/30) → {dates[], sessions[], resolved[]} |
| GET | /api/dashboard/top-questions | 高频问题 | {questions[], count} |

### 4.5 系统设置接口

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| GET | /api/settings/bot | 获取机器人设置 | — |
| PUT | /api/settings/bot | 更新机器人设置 | {welcome_message, confidence_threshold, transfer_rules} |
| POST | /api/settings/reset-demo | 加载演示数据（冷启动，灌入 seed 会话/知识缺口） | — |

### 4.6 多租户买家端接口（/api/public，按 company_id 路由）

| 方法 | 路径 | 说明 | 响应 |
|------|------|------|------|
| GET | /api/public/config | 按 company_id 返回买家端欢迎语与阈值 | {welcome_message, confidence_threshold} |
| POST | /api/public/chat | 买家端 AI 对话（路由到对应商家知识库） | {reply, sources, confidence, need_human} |
| POST | /api/public/transfer | 买家主动转人工 | {status} |
| GET | /api/public/conversations/{id} | 买家拉取自己会话的消息 | {messages[]} |

### 4.7 坐席协同与评测接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/conversations/{id}/ai-suggest | 手动触发 AI 回复建议 |
| POST | /api/conversations/{id}/suggestions/{sid}/accept | 采纳 AI 建议（一键发给买家） |
| POST | /api/conversations/{id}/suggestions/{sid}/reject | 忽略 AI 建议 |
| POST | /api/conversations/{id}/accept | 坐席接入待人工会话 |
| POST | /api/eval/run | 运行 RAG 评测（67 题分层 golden set，输出混淆矩阵 + 转人工判断准确率） |
| POST | /api/knowledge/gaps/{id}/resolve | 解决知识缺口（写入标准答案并关闭） |
| POST | /api/knowledge/gaps/{id}/ignore | 忽略知识缺口 |

---

## 五、核心业务流程（时序图）

### 5.1 AI问答主流程

```
买家 → 前端: 发送问题
前端 → FastAPI: POST /api/chat {message, session_id?}
FastAPI → ChatHistory: 获取最近5轮对话历史
FastAPI → RAG Retriever: 语义检索Top-3相关文档片段
RAG Retriever → FAISS: 向量相似度搜索
FAISS → RAG Retriever: 返回Top-3片段+来源文档名
FastAPI → Confidence Scorer: 计算置信度(检索得分×长度系数×有无来源)
FastAPI → LLM API: 发送prompt(系统指令+历史+检索片段+用户问题)
LLM API → FastAPI: 返回回答
FastAPI → 数据库: 保存message(含sources, confidence, need_human)
FastAPI → 前端: {reply, sources, confidence, need_human}
前端 → 买家: 展示回答+来源标签
    ├─ confidence < 0.6 → 显示"建议转人工"按钮（阈值由评测校准，见十二节）
    └─ confidence >= 0.6 → 正常展示
```

### 5.2 置信度与转人工判断

> ⚠️ **本节上半部分为设计意图；实际实现是简化版**，对照见下半部分。面试请按「实际实现」回答。

```
置信度 = 检索相关性得分 × 回答长度系数 × 是否包含来源      ← 设计意图
        (0-1)        (0.8-1.0)        (0或1)

转人工触发条件（设计意图，满足任一）：
1. confidence < 0.6
2. 连续2次拒答（检索无结果）
3. 用户消息包含"人工"/"客服"/"投诉"等关键词
4. 情绪检测为负面（简单关键词匹配：生气/投诉/差评/举报）
```

**实际实现（与代码一致，以 `backend/app/services/ai_suggestion.py::_calc_confidence` 为准）：**

```
置信度 = 无检索结果 → 0.25
        有检索结果 → 0.4 + avg(top-3 相似度) × 0.55，截断在 0.1–0.95

转人工触发条件（实际，满足任一）：
1. 检索置信度 < company_settings.confidence_threshold（默认 0.6，由 67 题评测集校准）
2. 高危关键词正则命中（投诉/辱骂/律师/起诉/曝光/报警/工商/消协/315）
   → 在进入 LLM 之前拦截，0 次 LLM 调用
3. 工具返回 needs_human=True（calc_refund 退款试算恒为 True；transfer_to_human 恒为 True）
4. 会话状态已为 waiting_human → 后续消息走人工建议分支
```

> **已知差异（如实记录）**：设计稿里的「回答长度系数」「是否包含来源」「连续拒答计数」「情绪检测」**在实际实现中未落地**，简化为纯检索分数的线性映射。这是「设计意图 > 实际实现」的典型差异，追问时按实际说明，不要按设计稿回答。

### 5.3 文档上传与索引流程

```
商家 → 前端: 上传PDF/TXT/DOCX
前端 → FastAPI: POST /api/knowledge/upload (multipart)
FastAPI → 文件系统: 保存文件到 knowledge/{user_id}/
FastAPI → DocumentParser: 解析文本(PDF→PyPDF2, DOCX→python-docx)
FastAPI → TextSplitter: 按段落切分(每块500字, 重叠50字)
FastAPI → Embedding模型: 逐块向量化(sentence-transformers)
FastAPI → FAISS: 添加向量到索引
FastAPI → 数据库: 保存document记录(status=ready)
FastAPI → 前端: 返回上传成功
```

---

## 六、AI引擎设计（RAG Pipeline）

### 6.1 核心模块划分

```
src/
├── core/
│   ├── retriever.py      # FAISS检索器（加载索引、语义搜索、返回Top-K）
│   ├── generator.py      # 回答生成器（构建prompt、调用LLM API、解析响应）
│   ├── confidence.py     # 置信度评分（检索得分×长度系数×来源判断）
│   ├── chat_history.py   # 对话历史管理（最近5轮，滑动窗口）
│   ├── document_parser.py # 文档解析（PDF/TXT/DOCX→纯文本）
│   ├── text_splitter.py  # 文本切分（段落优先，500字/块，重叠50字）
│   └── transfer.py       # 转人工判断（置信度/关键词/情绪/连续拒答）
├── knowledge/            # 知识库文件存储（按user_id分目录）
├── faiss_index/          # FAISS索引文件（按user_id分目录）
└── ...
```

### 6.2 Prompt模板

```
系统指令：
你是小云智服，一个服饰电商售后客服助手。请根据以下检索到的店铺售后政策文档回答用户问题。
要求：
1. 只基于检索到的文档内容回答，不要编造政策
2. 如果文档中没有相关信息，回答"抱歉，这个问题我需要帮您转接人工客服"
3. 回答简洁专业，不超过200字
4. 涉及退换货、运费、时效等关键信息时，标注来源文档名

检索文档：
{retrieved_chunks}

对话历史：
{chat_history}

用户问题：{user_message}
```

### 6.3 防幻觉机制

1. **检索兜底**：如果Top-3检索得分都低于阈值(0.3)，直接拒答转人工，不调用LLM
2. **Prompt约束**：明确指令"只基于文档回答，不要编造"
3. **来源校验**：生成后检查回答中的关键信息是否在检索片段中出现（简单关键词匹配）
4. **拒答模板**：超纲问题统一回复拒答话术+转人工建议

---

## 七、前端页面清单（25页规划）

> **对照真实代码：** 前端目前约 10 个路由，下表是规划全集。已实现 / 部分实现 / 规划未做见 `docs/功能全景-给协作方.md` 第三节。不要把下表当成「每一页都已上线」。

### 7.1 公共页面（2页）
| 序号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 1 | 登录页 | /login | 邮箱密码登录 |
| 2 | 注册页 | /register | 企业注册（公司名+邮箱+密码） |

### 7.2 买家端（1页，手机尺寸）
| 序号 | 页面 | 说明 |
|------|------|------|
| 3 | 买家对话页 | 手机端聊天界面，AI回答+来源标签+转人工按钮 |

### 7.3 商家端管理后台（22页，桌面尺寸）

**核心业务（8页）：**
| 序号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 4 | 数据总览 | /dashboard | 核心指标卡+趋势图+高频问题 |
| 5 | 会话管理 | /sessions | 会话列表（筛选/搜索/批量操作） |
| 6 | 会话详情 | /sessions/:id | 完整对话记录+人工接管 |
| 7 | 转人工队列 | /transfer-queue | 待接入的人工会话 |
| 8 | 工单中心 | /tickets | 售后工单列表+状态流转 |
| 9 | 工单详情 | /tickets/:id | 工单详情+SLA预警 |
| 10 | 快捷话术库 | /quick-replies | 分类管理常用回复 |
| 11 | 通知中心 | /notifications | 系统通知+异常告警 |

**知识库（5页）：**
| 序号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 12 | 知识库管理 | /knowledge | 文档列表+分类筛选+上传 |
| 13 | 文档上传与解析 | /knowledge/upload | 拖拽上传+解析进度 |
| 14 | 文档分类管理 | /knowledge/categories | 分类树管理 |
| 15 | 低置信度审核 | /review-queue | AI回答质量审核 |
| 16 | 知识缺口处理 | /knowledge/gaps | 未命中问题→补充知识闭环 |

**AI治理（4页）：**
| 序号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 17 | AI效果分析 | /ai-analytics | 准确率/拒答率/响应时间/溯源命中率 |
| 18 | 答案出处溯源 | /source-trace | 回答→文档片段映射查看 |
| 19 | 评测基线 | /evaluation | 评测集管理+对比实验+消融实验 |
| 20 | 版本迭代记录 | /changelog | 模型/知识库版本变更记录 |

**系统设置（5页）：**
| 序号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 21 | 机器人设置 | /settings/bot | 欢迎语/置信度阈值/转人工规则 |
| 22 | 团队管理 | /settings/team | 成员列表+角色权限 |
| 23 | 用量统计 | /settings/usage | API调用次数/Token消耗/套餐余量 |
| 24 | 个人设置 | /settings/profile | 个人信息+密码修改 |
| 25 | 组件库与状态页 | /components | UI组件展示（开发参考，可不放导航） |

---

## 八、开发计划（分模块，按顺序执行）

### 阶段A：项目骨架（优先级P0）
1. 初始化项目结构（前端React+Vite，后端FastAPI）
2. 配置Tailwind CSS + 视觉规范（青绿#1D9E75主色）
3. 数据库初始化（SQLAlchemy模型+建表）
4. JWT认证实现（注册/登录/获取当前用户）
5. 布局骨架（侧边栏220px+顶部栏64px+内容区）

**验收：** 能注册登录，进入空白管理后台，侧边栏导航可切换

### 阶段B：AI引擎核心（优先级P0）
6. 文档解析模块（PDF/TXT/DOCX）
7. 文本切分+向量化+FAISS索引
8. RAG检索器（Top-K语义搜索）
9. LLM回答生成（prompt模板+API调用）
10. 置信度评分模块
11. 对话历史管理（滑动窗口）
12. 转人工判断模块

**验收：** 上传一份售后政策PDF后，能通过API提问并获得带来源的回答，低置信度问题标记转人工

### 阶段C：知识库管理（优先级P0）
13. 文档上传API+前端页面
14. 文档列表+删除+分类
15. 知识缺口记录与处理页面

**验收：** 商家能上传/删除/分类管理文档，系统自动记录未命中问题

### 阶段D：对话与会话（优先级P0）
16. 聊天API（/api/chat，整合AI引擎）
17. 会话列表API+前端页面
18. 会话详情页（完整对话记录）
19. 转人工功能
20. 买家端对话页（手机尺寸，独立路由或嵌入iframe）

**验收：** 买家能提问获得AI回答，商家能在后台看到所有会话并查看详情

### 阶段E：数据看板（优先级P1）
21. 核心指标统计API（FCR/转接率/响应时间/满意度）
22. 趋势数据API
23. 数据总览页面（指标卡+图表）
24. AI效果分析页面

**验收：** 数据看板能展示真实的会话统计数据

### 阶段F：系统设置与收尾（优先级P1）
25. 机器人设置页面
26. 团队管理页面
27. 用量统计页面
28. 快捷话术库
29. 工单中心（简化版）
30. 整体UI打磨+响应式适配

**验收：** 所有页面可访问，核心流程完整可跑通

---

## 九、输出规范（每次开发必须遵守）

### 9.1 每轮开发前
1. 先列出本轮要改哪些文件、不改哪些文件
2. 说明本轮要实现的功能点
3. 等待确认后再开始（或按任务清单逐项执行）

### 9.2 每轮开发后
1. 汇报变更内容（改了哪些文件、实现了什么功能）
2. 说明如何验证（启动命令、测试步骤）
3. 列出已知问题和下一步计划
4. 在开发计划对应项打勾

### 9.3 代码规范
- 后端：每个API端点写docstring，包含请求/响应示例
- 前端：组件命名PascalCase，页面文件放在pages/目录
- 配置：API密钥等敏感信息放.env文件，不硬编码
- 注释：核心算法（置信度计算、切分策略）加中文注释

### 9.4 回滚方案
- 使用git分支管理，每个阶段一个分支
- 开发前先commit当前状态，做坏了可回退
- 数据库变更写迁移脚本，不直接改表结构

### 9.5 测试要求
- 每个API端点用curl或FastAPI docs测试
- AI引擎：准备10条测试问题，验证回答质量和置信度
- 前端：核心流程手动测试（注册→登录→上传文档→提问→查看会话→看看板）

---

## 十、启动方式

### 后端启动
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
API文档：http://localhost:8000/docs

### 前端启动
```bash
cd frontend
npm install
npm run dev
```
访问：http://localhost:3000

### 环境变量（.env）
```
DATABASE_URL=sqlite:///./xiaoyun.db
LLM_API_KEY=your_zhipu_api_key
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4-flash
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
JWT_SECRET=your_jwt_secret
```

---

## 十一、与原型HTML的对应关系

v1已有18页HTML原型在 `成品包/02_原型HTML/` 目录下，开发前端时：
1. **参考其布局和视觉**（侧边栏、卡片、配色），但用React组件重写
2. **参考其数据展示方式**（指标卡、表格、对话气泡）
3. **补充缺失的7页**（注册、历史会话、快捷话术、团队管理、用量统计等）
4. **买家端对话页改为手机尺寸**（375px宽，模拟真实手机聊天界面）

---

## 十二、已实现功能迭代记录（截至 2026-08-25）

> 以下为 v1.0 PRD 之后由 AI 编码工具实现的真实提交（git log 可查），作为作品集面试复盘依据。**均为演示态（Demo）能力，非生产上线。**

| 提交 | 功能 | 说明 |
|------|------|------|
| 6bde644 | 买家转人工体验、错误处理与演示数据冷启动 | 转人工流程打磨；API 错误统一兜底；`reset-demo` 一键灌入 seed 会话/知识缺口 |
| 7a0bd6f | 升级 67 题评测集与转人工判断指标 | 分层 golden set + 混淆矩阵；**由评测校准置信度阈值至 0.6**（当时口径：转人工判断 97%、"回答准确率" 91.1%、检索命中 100%、误转 1.8%、漏转 9.1%）⚠️ 其中「回答准确率 91.1%」为**检索关键词覆盖率代理指标**，口径已于 2026-09-21 修订，见 **12.3** |
| f56c485 | 买家进线昵称与会话协同体验优化 | 买家昵称进线；待人工会话角标提醒 |
| f97a94b | 多租户接入、知识缺口闭环与坐席协同提醒 | company_id 路由的公开买家入口（`/api/public/*`）；设置页可复制买家链接；知识缺口写入；工单可看原会话；Header 待人工提醒 |
| e32f8f8 | 会话内一键写入知识库并清除切换残留状态 | 坐席可将 AI 标准回复一键写入知识库并关闭对应缺口；切换会话时清空残留输入/编辑状态，避免串台 |
| 0335589 | **新增 `knowledge_search` / `human_transfer` 工具，完善意图路由与工具注册** | 工具注册表扩展出 `parameters`（JSON Schema）与 `to_openai_schema()`；4 个工具就位 |
| 921964c | embed_text 增加 3 次重试与指数退避 | 避免瞬时网络抖动导致整条 AI 回复失败 |
| 12724e7 | **新增消融评测脚本（裸模型 vs RAG 双臂）** | `backend/scripts/eval_baseline.py`；判定对象改为**生成的回答文本**（不再是检索片段），含 usage / P50-P95 / 成本折算 |
| 41def67 | **与售后无关的话题强制调用 `transfer_to_human`** | 修复 Agent 改造后超范围题不转人工的问题（详见 14.6） |
| 66a92dc | 新增评测报告 `eval_report.md` | 消融对照 + 成本 + 延迟汇总；**修订简历口径**（详见 12.3） |

> **Agent 控制层改造（第十四节）** 的完整设计与实测记录见本文件第十四节。

**评测口径说明（面试红线）：** 上述准确率为历史 67 题评测集（合成 golden set）口径，不等于线上真实解决率；当前正式回归集为 40 题，真实 query 分布需上线后回流，这是已知的"数据飞轮"下一步。

### 12.1 历史 67 题评测集结构（归档；当前 `eval/questions.json` 为 40 题）

文件头的「含原 17 题」只是演进说明；**本节 67 题数据为历史归档，现行正式总量为 40**。

| 分层维度 | 取值 | 用途 |
|----------|------|------|
| `category` | 退换货 10 / 物流 10 / 质量 10 / 支付 10 / 通用 10 / 超出范围 11 / 尺码 3 / 售后政策 3 | 看哪类场景误转、漏转 |
| `difficulty` | easy / normal / hard | 分析难例，不作发版硬门槛 |
| `expected_behavior` | `answer`（56）或 `transfer_human`（11，均为超出范围类） | **核心标签**：该答还是该转 |
| `expected_keywords` | 关键词列表 | 充当「golden」的可判定部分，**不是**整段标准答案范文 |

实现：`backend/app/services/eval_runner.py`。

**评分 rubric（与代码一致）：**

1. **检索命中**：Top-K 有任意结果即 hit（召回率口径偏宽，面试要自己说清）。
2. **实际行为**：`confidence < threshold` 或 **无检索结果** → `transfer_human`，否则 `answer`（与买家端阈值逻辑对齐）。
3. **转人工判断准确率**：`actual_behavior == expected_behavior` 的题数 / 67。
4. **回答准确率**（仅 `expected_behavior=answer`）：检索命中，且关键词命中率 ≥ 50%（`len(hits)/len(keywords)`）。无关键词则退化为「检索到即算过」。
5. **混淆矩阵**：误转 = 该答却转了；漏转 = 该转却答了。

评测跑的是 **检索 + 阈值行为**，**不调用 LLM 生成全文**，因此「回答准确」≈ 资料是否覆盖关键词，不是人工读生成质量。

### 12.2 置信度 0.6 的校准方法

置信度公式（`ai_suggestion._calc_confidence`）：无检索 → 0.25；有结果则 `0.4 + avg(top-3 score) * 0.55`，截断在 0.1–0.95。

校准原则（作品集已落地口径）：

1. 用 **67 题** 在候选阈值上扫一遍（实现上默认写入 0.6，历史对比：0.4 低于当时最低有效分，安全网几乎不触发）。
2. 优化目标不是「回答准确率最高」，而是 **转人工判断**：宁可略增误转，也要压漏转（客诉风险）。
3. 选定 **0.6** 后写入 `company_settings.confidence_threshold` 默认值；评测报告当时口径：转人工判断约 97%、"回答准确率"约 91.1%、检索命中 100%、误转 1.8%、漏转 9.1%（以本地最新 `/api/eval/run` 为准）。该 91.1% 的口径问题与修订见 **12.3**。

面试说法：0.6 是评测闸门上的工作点，不是行业标准常数。

### 12.3 评测口径修订（2026-09-21）—— 为什么弃用「回答准确率 91.1%」

**旧口径的真实含义**：在 56 道 `answer` 类题上，统计**检索返回的资料片段**是否包含 `expected_keywords`（覆盖率 ≥ 50%），**全程未调用 LLM 生成任何回答**。
验算：51 / 56 = 91.07% ≈ **91.1%**。
→ 它是**检索代理指标**，回答的是"资料搜到了没"，**不是**"AI 答得对不对"。

**新口径**：判定**模型生成的回答文本**是否命中关键词；并新增 **baseline 臂**（不给资料、直接问模型）做消融对照，使"RAG 到底贡献了什么"可归因。

**实测结果（67 题 × 2 臂，完整报告见 `eval/eval_report.md`）**：

| 指标 | 裸模型（无资料） | RAG（有资料） | 差值 |
|---|---|---|---|
| **人机分流判断准确率** | **0.00%** | **90.91%** | **+90.91pp** |
| 回答准确率（56 题） | 94.64% | 92.86% | −1.78pp |
| 整体准确率（67 题） | 79.10% | 92.54% | +13.44pp |
| 平均 tokens / 次 | 176.74 | 689.45 | +512.71 |
| P50 / P95 延迟 | 4831 / 9638 ms | 4832 / 8700 ms | — |
| 实际 LLM 调用次数 | 66 | 56 | −10 |

**三条结论（面试口径）**：

1. **RAG 的价值不体现在"答得更准"**：常规售后问答上 94.64% vs 92.86%，RAG 未显著提升——题目偏常规，模型凭常识即可作答。`normal` 难度桶里 RAG 的 answer 反而少 3 题（29/29 → 26/29），说明把资料原文直接塞进 prompt 对常规问题可能产生**干扰**，这是"检索结果怎么用"的优化空间，不是"检索有没有用"。
2. **RAG 不可替代的是私域政策准确性与人机分流能力**：裸模型根本没有"该不该转人工"这个概念，11 道超范围题**全部照答**（0%）；RAG 版靠"检索不到 → 置信度低于 0.6 → 强制转人工"接住 10 道（90.91%）。
3. **分流本身就省成本**：RAG 版实际 LLM 调用 56 次 < 裸模型 66 次——每拦下一次无效生成就省一次 token。

**写作红线**：不得写"RAG 提升回答准确率"（数据不支持）；「回答准确率 91.1%」已废弃。

**本次评测的局限（如实声明）**：

- 判定用的是关键词命中率代理指标，不是人工评分，存在假阴/假阳；
- RAG 臂走**传统检索链路**（`search_knowledge` + 阈值），**未走新的 Agent 全链路**——本次对照测的是"知识库的价值"，**不含** Agent 工具调用能力；
- **embedding 检索成本未计入**（`embedding-3` 为独立付费通道，每次提问至少 1 次调用）；
- 1 条样本因 SSL 瞬时断连失败未重跑；
- 样本量 67，分位数仅用于展示方法论，不构成生产级性能承诺。

---

## 十三、技术 Spec：多租户隔离、LLM 降级、MVP DoD

### 13.1 多租户数据隔离（A/B 商家）

**路由**

- 坐席 API：`get_current_user` → `current_user.company_id`，查询一律带该字段（会话、工单、知识库、缺口、设置、评测）。
- 买家公开 API：`/api/public/*` 用 query/body 的 `company_id`，缺省回退 `DEFAULT_COMPANY_ID`（默认 1）。会话创建/拉消息时 `Conversation.company_id == 解析出的 cid`，A 的 `conversation_id` 不能读 B 的消息。

**数据与索引**

- 业务表：`conversations` / `knowledge_docs` / `knowledge_gaps` / `tickets` / `company_settings` 均有 `company_id`。
- 向量：`VectorStore(company_id)` → `company_{id}.index` + `.meta.json`，检索不跨公司。

**A/B 场景（演示）**

1. 商家 A 登录复制 `/chat?company_id=A`，买家进线只进 A 的会话与知识库。
2. 商家 B 同理。B 的文档不会出现在 A 的 RAG 来源里。
3. 已知限制：`company_id` 出现在 URL 上，**不是密钥**；知道 ID 即可打到该租户公开入口。演示级隔离，不是零信任 SaaS。无行级加密、无独立库。

**PII**

- 存：买家昵称、对话原文、坐席账号邮箱。
- 原则：字段最小化；默认不拿对话微调模型；转人工只在同公司会话内。
- 未做：脱敏中间件、留存到期清理任务、加密列。面试按「设计原则已写、工程未做完」说。

### 13.2 LLM 失效 / 超时 / 限流的降级

| 场景 | 代码行为 |
|------|----------|
| 未配置 `LLM_API_KEY` | `ValueError`；买家咨询路径走拒答话术并转人工；坐席建议卡写入「未配置」文案 |
| HTTP 失败 / 超时（LLM 60s，embedding 30s） | `ExternalServiceError`；`/api/public/chat` 可 502；咨询生成失败则拒答+`waiting_human` |
| 响应 JSON 畸形 | 同上 ExternalServiceError |
| 高危关键词拦截 | 纯正则（`detect_high_risk`），不依赖 LLM，不存在"失败"场景 |
| 工具调用失败 | 工具返回 `ok=false` → 失败信息回灌给模型，由模型决定追问或转人工 |
| RAG/embedding 失败 | 检索当空 → 低置信 → 转人工或缺口记录 |
| 限流 | 无独立 429 重试队列；表现为 HTTP 失败 → 同一套降级 |

原则：**宁可不答、转人工，也不编政策。** 退款工具本身不调 LLM。

### 13.3 项目 DoD（本仓库 MVP 完成的定义）

下列全部满足，视为 **Demo MVP Done**（不是生产上线）：

1. **双端闭环**：买家能问到带来源的回答；低置信能进待人工；坐席能接入并回复；买家能刷到人工消息。  
2. **知识闭环**：低置信记缺口；会话内或知识库页能写入文档并索引。  
3. **评测闸门**：`/api/eval/run` 可跑 **67 题**，产出转人工判断与混淆矩阵；默认阈值 0.6。  
4. **隔离雏形**：JWT + `company_id` 过滤 + 分索引；公开入口可带 `company_id`。  
5. **降级**：无 Key / API 挂时系统不静默编造，走拒答或转人工。  
6. **文档一致**：定位 / 评测题量 / 单一价 ¥299/月 与 `docs/功能全景-给协作方.md` 一致。  
7. **明确非 DoD**：独立转人工队列页、工单详情页、团队管理、用量统计、个人设置、AI 效果分析独立页、答案溯源独立页、真实订单/支付、生产级多租户密钥。

未完成第 7 条中的页面，**不阻塞**「MVP 可演示」；阻塞项是 1–6。

---

## 十四、Agent 控制层：从「意图硬路由」到「模型自主工具调用」（2026-09-21）

### 14.1 为什么要改

改造前，买家消息进入后的处理逻辑是：

```
分类意图（调 1 次 GLM 做 4 分类）→ 代码 if/elif 按分类结果挑分支
  transfer → 直接拒绝话术
  query    → 调 query_order
  action   → 先 query_order 再 calc_refund
  consult  → RAG 检索 + 生成
```

三个问题：

1. **每轮对话固定消耗 2 次 LLM 调用**（先分类、再生成），成本与延迟翻倍。
2. **决定权在代码不在模型。** 模型明明能理解语言，却被限制成"只能输出一个分类标签"，再由 `if/elif` 翻译成"调哪个工具"。**每加一个新能力就要多写一个分支。**
3. **实测出稳定性问题。** `traces.jsonl` 里出现过同一句"发什么快递"，会话 16 判为 `query`（去查了订单，返回 DEMO-1001 物流）、会话 17 判为 `consult`（正确回答了快递政策）——**同一输入两次判定不同**。根因是分类环节有两套逻辑打架（LLM 判定 vs 关键词覆盖，`source` 字段暴露了这一点）。

**改造目标**：把"该做什么"的决定权从代码交给模型；代码只负责**执行模型选的工具**与**卡死安全红线**。不推翻现有 RAG 检索/生成逻辑。

### 14.2 新架构执行流程

```
买家消息
  │
  ├─ ① 会话已在 waiting_human → 走人工建议分支（不进入下面的循环）
  │
  ├─ ② 高危关键词前置拦截 detect_high_risk()
  │     命中投诉/辱骂/律师/起诉/曝光/报警/工商/消协/315
  │     → 直接转人工，llm_calls = 0
  │
  └─ ③ function calling 主循环（最多 MAX_TOOL_ROUNDS = 4 轮）
        messages = [system(工具使用规则) + history + user]
        loop:
          resp = llm.complete(messages, tools = list_tool_schemas())
          if resp.tool_calls 为空 → 使用 resp.content 作为终答，break
          for call in resp.tool_calls:
              结果 = run_tool(call.name, 原始用户消息, **call.args)
              messages.append(tool 角色消息：结果)
              if 结果.needs_human:
                  → 硬中断：立刻 break 进入人工分支，
                    不再追加一轮 LLM（模型无权继续）
```

### 14.3 四个工具（`backend/app/agent/tool_registry.py`）

| 工具 | 用途 | 参数（JSON Schema） | `needs_human` |
|---|---|---|---|
| `search_policy` | 查店铺政策/规则（包装 `search_knowledge` + 置信度） | `query`（必填） | 随置信度，低于 0.6 时为 true |
| `query_order` | 查订单状态与物流 | `order_id`（选填） | 恒 false |
| `calc_refund` | 退款试算（纯规则） | `order_id` / `amount` / `days_since_purchase`（均选填） | **恒 true（强制人工确认）** |
| `transfer_to_human` | 转人工 | `reason`（必填） | **恒 true** |

`ToolSpec` 扩展出 `parameters`（JSON Schema）与 `to_openai_schema()`，直接产出可放进请求 `tools` 字段的结构；`list_tools()` / `run_tool()` 原签名保持不变，**向后兼容**。

### 14.4 安全红线：靠代码，不靠提示词

**这是本次改造最重要的设计原则。** 退款与转人工的判断权不接受模型自主决定：

| # | 约束 | 实现位置 |
|---|---|---|
| 1 | **系统里不存在"执行退款"的工具**，模型物理上调不到会打款的函数，只能"试算" | `tools/refund_calc.py` 只做规则计算，无写操作 |
| 2 | 工具返回 `needs_human=True` → **代码立刻中断循环**，不追加一轮 LLM 去问"你接下来想说什么" | `agent_loop.py` 主循环 |
| 3 | 投诉/辱骂/法律类高危词在**进 LLM 之前**用正则拦掉 | `intent_router.detect_high_risk()` |

**为什么不靠提示词**：提示词约束可以被模型绕过（见 14.6 实测）；代码判断不会。

### 14.5 关键设计决策

**① 废弃 LLM 意图分类，只保留高危正则拦截。**
- 省一次 LLM 调用：简单咨询场景从 **2 次 → 1 次**。
- 高危场景全程 **0 次 LLM**：更安全（情绪激动的客户不该让 AI 接）、更省钱、更快。
- 正则范围有意收窄：**只拦投诉/法律/曝光类，把「穿过/污损」摘出去**交给 `calc_refund` 判断——否则"穿过沾了粉底液能退吗"会在进模型前被拦死，**退款试算 + HITL 确认卡这条演示路径永远不会被触发**。

**② `query_order` 的隐藏兜底改为显式开关。**
原实现：用户没给单号时，代码 `found = orders[0]` **偷偷返回第一条订单**。演示效果好，但与"模型自主决策"冲突——模型会学成永远不传 `order_id`。改为 `fallback_to_first` 参数（默认关），未命中单号时返回 `need_order_id=True`，由模型主动追问。

**③ `intent_router.py` 保留但降级。** 原 4 分类（`classify_intent` / `CLASSIFY_PROMPT` / `_keyword_intent`）已删除，文件缩为 1 个纯正则函数。

**④ 出参契约不变。** `PublicChatResponse` 的 `intent` / `plan_steps` 字段**保留 key 不删**（前端「执行计划卡」依赖它渲染），仅语义调整：`intent` 改为"模型实际调用了哪些工具"，如 `direct_answer` / `query_order+calc_refund`。

**⑤ 知识缺口回流重新挂钩。** 原 `record_knowledge_gap()` 埋在 `_run_consult()` 里，该函数被循环替换后会丢失；现改挂在 `search_policy` 分支内，自迭代闭环保持完整。

### 14.6 实测记录：模型不调工具 ≠ 不会调工具

把"超范围话题"改为强制转人工时，踩了一个坑，值得记录：

| 改动 | 结果 |
|---|---|
| 只在系统提示里写"超范围问题请礼貌说明你只能处理售后" | ❌ 模型**用嘴拒绝了**（回"建议您使用专门的编程社区"），但 `need_human=False`——**它没调工具** |
| 把"是否属于售后范畴"提为**最高优先级前置判断** + 显式写明"**禁止只用文字说我帮不了您来代替调用工具**" + 删除原规则里"能直接回答就直接回答"的放行口子 | ✅ 正确调用 `transfer_to_human` |

**结论**：模型不调工具，不是"不会调"，而是"**它没觉得有必要调**"——它愿意用嘴拒绝，不愿意用手办事。所以提示词必须堵掉"用嘴拒绝"这条退路。GLM-4-Flash 这类轻量模型指令遵循较弱，**规则冲突时会挑宽松那条执行**（原第 6 条就是模型的逃跑借口）。

**验收（直连 `run_agent_turn` 脚本测试）**：

| 输入 | 期望 | 结果 |
|---|---|---|
| 帮我写一段 Python 排序算法代码 | 转人工 | ✅ `transfer_to_human` / `need_human=True` |
| 今天北京天气怎么样？ | 转人工 | ✅ `transfer_to_human` / `need_human=True` |
| 你好 | 直接回答（**反向测试防误伤**） | ✅ `direct_answer` / `need_human=False` |

### 14.7 会话轨迹（`backend/data/traces.jsonl`）

每轮对话落一条 JSON，字段：

| 字段 | 含义 |
|---|---|
| `ts` / `conversation_id` / `company_id` | 时间与会话定位 |
| `input` | 买家原始输入 |
| `intent` | 模型决策摘要（含 `source`：`high_risk_regex` / 工具集） |
| `tools` | 调用了哪些工具、传了什么参数、返回摘要 |
| `llm_calls` | 本轮 LLM 调用次数（高危拦截为 0） |
| `needs_human` / `pending_confirmation_id` | 是否人工介入 |
| `interrupt_reason` | 中断原因（如 `low_confidence_rag`） |
| `grounded` | 回答是否有检索资料支撑 |
| `output` | 最终回给买家的话 |

**价值**：Agent 会自己决策，出错就必须能回放"它当时为什么这么判断"。这也是 badcase 复盘与面试演示的核心材料。

### 14.8 涉及文件

| 文件 | 改动 |
|---|---|
| `backend/app/services/llm.py` | 新增 `LLMResult`（content / tool_calls / usage / latency_ms）与 `complete(tools=...)`；`chat()` 保留原签名内部委托 |
| `backend/app/agent/tool_registry.py` | `ToolSpec` 加 `parameters` + `to_openai_schema()`；新增 `list_tool_schemas()`；注册 4 工具 |
| `backend/app/agent/agent_loop.py` | 主循环替换 if/elif；新增 `AGENT_SYSTEM_PROMPT`、`MAX_TOOL_ROUNDS`、`_do_transfer()`、`_build_refund_pending()` |
| `backend/app/agent/intent_router.py` | 删除 4 分类，缩为 `detect_high_risk()` |
| `backend/app/agent/tools/knowledge_search.py` | **新增**（包装 `search_knowledge`） |
| `backend/app/agent/tools/human_transfer.py` | **新增**（恒 `needs_human=True`） |
| `backend/app/agent/tools/order_query.py` | 新增 `fallback_to_first` 开关与 `need_order_id` 返回 |
| `human_review_actions` | **已替代旧 pending_confirmations.json**（确认状态进入数据库；仍需补过期/并发策略） |

**不受影响的模块**：`knowledge.py` / `conversations.py` / `tickets.py` / `stats.py` 及前端 Dashboard、Tickets、Conversations、Knowledge、Evaluation 页面——出参契约未变。本次改造是 `agent/` 包内的增量改动。

### 14.9 已知局限

1. **无自动化测试兜底**，验收靠手工跑场景 + 读 traces。
2. 旧 `pending_confirmations.json` 已不再作为运行时状态源；`human_review_actions` 仍无过期机制、无锁，属于当前已知取舍。
3. **Agent 工具调用能力未纳入自动化评测**：67 题评测集只覆盖"该答 / 该转"，不覆盖"该调哪个工具"，需补一份工具选择小样本题库。
4. 主循环中 `confidence` 对 `query_order` 命中时保留默认展示值 0.7，与工具真实返回值不同源（仅影响前端展示数值）。
5. `run_tool(name, message, company_id=..., fallback_to_first=False, **args)`：若模型在 args 里传入同名参数会触发 duplicate kwarg——当前 schema 未暴露这两个字段，属潜在坑。

