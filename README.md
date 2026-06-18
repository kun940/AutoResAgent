# AutoRes Agent — 客诉自动回复与质量追溯系统

基于大模型 Agent 的客户投诉自动回复、智能定级、工单归档与质量追溯系统。

## 项目简介

本系统采用 C/S 架构，通过 4 步 Agent Pipeline（字段提取 → 业务定级 → RAG排障回复 → 路由分发）实现客诉的自动化处理。客户通过 H5 页面提交投诉后，系统自动完成结构化字段提取、紧急度定级、专业排障回复生成和工单路由分发，同时支持三级降级策略确保服务可用性。所有工单统一完整归档，留存全量客诉证据、Agent 研判记录与自动回复内容，支撑客户侧 H5 进度查询与企业生产侧质量追溯分析。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      客户端层                            │
│   企业桌面端（PyQt6）          客户H5页面（Vue3+Vant4）    │
└──────────────┬──────────────────────────┬───────────────┘
               │                          │
┌──────────────▼──────────────────────────▼───────────────┐
│                    服务层（FastAPI）                       │
│  /api/v1/tickets  /api/v1/customer  /api/v1/dashboard   │
│  /api/v1/auth     /api/v1/knowledge /api/v1/notifications│
└──────────────┬──────────────────────────┬───────────────┘
               │                          │
┌──────────────▼──────────────────────────▼───────────────┐
│                数据与AI层                                 │
│   MySQL 8.0    │  ChromaDB向量库  │  LangChain Pipeline  │
└──────────────┬──────────────────────────┬───────────────┘
               │                          │
┌──────────────▼──────────────────────────▼───────────────┐
│                   大模型层                                │
│     DeepSeek-V3（提取/定级）    QwQ-32B（回复生成）        │
└─────────────────────────────────────────────────────────┘
```

## 核心功能

- **Agent Pipeline 四步自动化处理**：Extractor（字段提取）→ Assessor（业务定级）→ Responder（RAG排障回复）→ Router（路由分发）
- **三级降级策略**：L0 正常（AI完整处理）→ L1 备选（关键词匹配+模板回复）→ L2 兜底（通用模板+标记人工）
- **工单完整归档**：全量留存客诉原文、Agent 提取结果、研判记录、自动回复内容、证据文件，归档完整性自动校验
- **客户 H5 进度查询**：客户通过 H5 页面随时查询工单处理进度（脱敏展示）
- **企业生产侧质量追溯**：按产品型号/批次/问题分类批量追溯，反向优化生产质检流程
- **企业桌面端**：登录/注册、主看板、客诉提交、工单列表（含证据图片查看/状态变更/升级/转派）、质量分析、系统设置
- **数据隔离**：客户侧脱敏展示，企业侧全量数据，JWT 认证保护
- **RAG 知识库**：ChromaDB 向量检索 + SOP 知识库，生成专业排障指导
- **工单生命周期**：pending → processing → routed → resolved → closed，支持 SLA 超时自动升级

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | MySQL 8.0（aiomysql 异步连接池） |
| AI 框架 | LangChain |
| 主模型 | DeepSeek-V3（提取/定级）、QwQ-32B（回复生成） |
| 向量库 | ChromaDB（PersistentClient）+ text2vec-base-chinese |
| 桌面端 | PyQt6 6.11.0 + Pillow |
| H5 客户页 | Vue 3 + Vant 4（CDN 引入） |
| ORM | SQLAlchemy 2.0（异步） |
| 认证 | JWT（python-jose + bcrypt） |

## 项目结构

```
AutoRes Agent/
├── backend/                    # 后端服务
│   └── app/
│       ├── api/                # API路由模块
│       │   ├── tickets.py      # 工单管理（提交/列表/详情/状态变更/升级/转派）
│       │   ├── customer.py     # 客户侧API（提交+查询，数据脱敏）
│       │   ├── quality.py      # 质量追溯（追溯查询/看板/导出）
│       │   ├── dashboard.py    # 看板统计
│       │   ├── auth.py         # JWT认证（登录+注册）
│       │   ├── knowledge.py    # SOP知识库CRUD
│       │   ├── notifications.py # 通知管理
│       │   └── upload.py       # 文件上传
│       ├── core/               # 配置、数据库连接
│       ├── middleware/          # JWT认证中间件
│       ├── models/             # SQLAlchemy ORM 模型（10张表）
│       ├── schemas/            # Pydantic 数据模型
│       ├── services/           # 业务逻辑层
│       ├── static/
│       │   ├── h5/             # H5客户页面（3个HTML）
│       │   └── uploads/        # 客户上传图片存储
│       └── main.py             # FastAPI 入口
├── agent/                      # AI Agent 引擎
│   ├── config/                 # LLM配置（模型分配、降级策略）
│   ├── core/                   # Agent核心
│   │   ├── extractor.py        # Step1: 字段提取（DeepSeek-V3）
│   │   ├── assessor.py         # Step2: 业务定级（DeepSeek-V3）
│   │   ├── responder.py        # Step3: RAG排障回复（QwQ-32B）
│   │   ├── router.py           # Step4: 路由分发（规则引擎）
│   │   └── agent_engine.py     # Pipeline编排引擎
│   ├── rag/                    # RAG模块
│   │   ├── sop_indexer.py      # SOP索引构建
│   │   ├── vector_store.py     # ChromaDB向量存储
│   │   ├── retriever.py        # 语义检索
│   │   └── embeddings.py       # text2vec-base-chinese嵌入
│   ├── multimodal/             # 多模态（图片分析预留）
│   └── prompts/                # Agent提示词模板
├── desktop/                    # 桌面端应用
│   ├── views/                  # 5个页面
│   │   ├── login_view.py       # 登录/注册
│   │   ├── dashboard_view.py   # 主看板
│   │   ├── submit_complaint_view.py # 提交客诉
│   │   ├── ticket_list_view.py # 工单列表（含图片查看/操作按钮）
│   │   ├── quality_analysis_view.py # 质量分析（追溯看板/报表导出）
│   │   └── settings_view.py    # 系统设置
│   ├── api_client.py           # HTTP API客户端
│   ├── resources/styles/       # QSS样式
│   └── main.py                 # PyQt6入口
├── shared/                     # 共享模块
│   ├── constants.py            # 枚举、状态流转、路由映射
│   ├── logger.py               # 日志工具
│   └── utils.py                # 通用工具
├── scripts/                    # 工具脚本
│   ├── init_db.py              # 数据库初始化（建9张基础表）
│   ├── migration_v1.1.sql      # v1.1迁移脚本（出单+质量追溯表）
│   ├── migration_v1.2.sql      # v1.2迁移脚本（删除出单表，改造追溯表）
│   ├── seed_data.py            # 种子数据（用户/路由规则/SOP）
│   ├── build_chroma_index.py   # 构建ChromaDB索引
│   └── download_model.py       # 下载嵌入模型
├── tests/                      # 测试
│   ├── test_agent/             # Agent验收测试（4场景）
│   ├── test_v1.1/              # v1.1/v1.2 接口与服务测试
│   └── test_v1.2/              # v1.2 归档与追溯测试
├── config/                     # 配置
│   ├── .env                    # 环境变量（不入Git）
│   └── .env.example            # 配置模板
├── data/                       # 运行时数据（不入Git）
│   └── chroma_db/              # ChromaDB持久化存储
├── prompts/                    # Agent提示词文档（开发用）
├── docs/                       # 项目文档
├── .gitignore
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 环境准备

| 软件 | 版本要求 | 用途 |
|------|---------|------|
| Python | 3.10+ | 后端服务、Agent引擎、桌面端 |
| MySQL | 8.0 | 数据库 |
| pip | 最新版 | 依赖管理 |

### 2. 安装

```bash
# 克隆项目
git clone <repo-url>
cd AutoRes Agent

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

```bash
cp config/.env.example config/.env
```

编辑 `config/.env`，填写以下必要配置：

```
# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的MySQL密码
DB_NAME=complaint_agent

# AI 模型 API Key
DEEPSEEK_API_KEY=你的DeepSeek API Key
DASHSCOPE_API_KEY=你的cucloud模型密钥

# 模型地址
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
QWEN_BASE_URL=https://aigw-nmhhht.cucloud.cn/v1
```

API Key 获取方式：
- **DeepSeek**：https://platform.deepseek.com 注册并创建 API Key（使用 deepseek-chat 模型）
- **QwQ-32B**：通过 cucloud 平台获取模型密钥，模型标识为 `Qwen/QwQ-32B`

### 4. 初始化数据库

```bash
python scripts/init_db.py      # 创建9张数据表
python scripts/seed_data.py    # 插入种子数据（4个用户、3条路由规则、6条SOP知识）
```

种子数据包含管理员账号：`admin / admin123`

### 5. 构建向量索引

```bash
python scripts/build_chroma_index.py   # 构建SOP知识库ChromaDB索引
```

首次运行需联网下载 `text2vec-base-chinese` 嵌入模型，后续自动使用本地缓存。

### 6. 启动

```bash
# 启动后端服务（端口8000）
python -m backend.app.main

# 启动桌面端（另一个终端）
python desktop/main.py
```

### 7. 访问

| 服务 | 地址 |
|------|------|
| 后端 API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |
| H5 客户页面 | http://localhost:8000/h5/ |
| 健康检查 | http://localhost:8000/health |

手机访问 H5：确保手机与电脑在同一 WiFi，浏览器打开 `http://<电脑IP>:8000/h5/`

## API 概览

### 企业侧 API（需 JWT 认证）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/login | 用户登录 |
| POST | /api/v1/auth/register | 用户注册 |
| POST | /api/v1/complaints/submit | 提交客诉（Form+File，支持图片） |
| GET | /api/v1/tickets | 工单列表（分页、按状态/紧急度筛选） |
| GET | /api/v1/tickets/{id} | 工单详情（含证据图片URL） |
| PUT | /api/v1/tickets/{id}/status | 变更工单状态 |
| POST | /api/v1/tickets/{id}/escalate | 升级工单紧急度 |
| POST | /api/v1/tickets/{id}/reassign | 转派工单（按角色+用户名） |
| GET | /api/v1/dashboard/stats | 看板统计数据 |
| GET | /api/v1/quality/trace | 质量追溯查询（按型号/批次/分类分组） |
| GET | /api/v1/quality/dashboard | 质量看板（概览/趋势/TOP5/分布） |
| GET | /api/v1/quality/export | 质量报表导出（CSV/XLSX） |
| GET | /api/v1/notifications | 通知列表 |
| GET | /api/v1/knowledge | SOP知识库列表 |

### 客户侧 API（无需认证，数据脱敏）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/customer/submit | 客户提交客诉（含图片上传，最多5张） |
| GET | /api/v1/customer/ticket/{id} | 客户查询工单（时间线格式，脱敏） |

## Agent Pipeline

| 步骤 | Agent | 主模型 | 功能 | 降级方案 |
|------|-------|--------|------|---------|
| Step 1 | Extractor | DeepSeek-V3 | 结构化字段提取（订单号/型号/批次/故障描述） | 正则表达式+默认值 |
| Step 2 | Assessor | DeepSeek-V3 | 分类/影响/紧急度/质保判定 | 关键词匹配 |
| Step 3 | Responder | QwQ-32B | ChromaDB检索SOP+生成排障回复 | 按分类选模板+标记人工 |
| Step 4 | Router | 规则引擎 | 紧急度→路由队列+指派处理人 | 静态映射表 |

> **注意**：QwQ-32B 是推理模型，输出包含思考过程。系统已自动剥离 `<think.../think>` 标签，确保客户只看到纯净的回复内容。

## 工单生命周期

```
pending → processing → routed → resolved → closed
                                    ↓
                              SLA超时自动升级
                    Low→Medium(48h) → Medium→High(24h)
```

状态流转规则：
- pending → processing / cancelled
- processing → routed / cancelled
- routed → resolved / cancelled
- resolved → closed

## 数据库表结构

共 10 张表（v1.2）：

| 表名 | 说明 |
|------|------|
| users | 系统用户（管理员/前线/部门经理/总经理/质检） |
| tickets | 工单主表（归档核心：客诉原文/提取结果/研判记录/自动回复） |
| evidence_files | 证据文件（图片/视频/文档） |
| ticket_logs | 工单操作日志 |
| routing_rules | 路由规则 |
| escalation_rules | 升级规则 |
| sop_knowledge_base | SOP知识库 |
| warranty_records | 质保记录 |
| notifications | 通知 |
| quality_trace_index | 质量追溯索引（v1.2: 解除去单外键，新增归档完整性字段） |

## 数据隔离策略

| 维度 | 客户侧（H5） | 企业侧（桌面端） |
|------|-------------|---------------|
| 认证 | 无需登录 | JWT Token 认证 |
| 可见字段 | 工单号/紧急度/状态/AI回复/时间线 | 全部字段含路由/处理人/SOP |
| 不可见字段 | routing_decision / assigned_to / sop_applied | — |
| 操作权限 | 提交 + 查询 | 状态变更 / 升级 / 转派 |

## 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|-------|------|
| DB_HOST | localhost | MySQL主机地址 |
| DB_PORT | 3306 | MySQL端口 |
| DB_USER | root | MySQL用户名 |
| DB_PASSWORD | 空 | MySQL密码 |
| DB_NAME | complaint_agent | 数据库名称 |
| DEEPSEEK_API_KEY | 空 | DeepSeek API密钥 |
| DASHSCOPE_API_KEY | 空 | cucloud模型密钥（QwQ-32B） |
| LLM_PRIMARY | deepseek | 主模型标识 |
| LLM_FALLBACK | qwen | 降级模型标识 |
| DEEPSEEK_BASE_URL | https://api.deepseek.com/v1 | DeepSeek API地址 |
| QWEN_BASE_URL | https://aigw-nmhhht.cucloud.cn/v1 | QwQ-32B API地址（cucloud代理） |
| LLM_TIMEOUT_SECONDS | 60 | LLM调用超时时间（秒） |
| CHROMA_PERSIST_DIR | ./data/chroma_db | ChromaDB持久化目录 |
| EVIDENCE_BASE_DIR | ./data/evidence | 证据文件存储目录 |
| FASTAPI_HOST | 0.0.0.0 | 后端监听地址 |
| FASTAPI_PORT | 8000 | 后端监听端口 |
| JWT_SECRET | dev-secret-change-in-production | JWT签名密钥（生产环境务必修改） |
| JWT_EXPIRE_HOURS | 24 | JWT令牌过期时间 |

## 常见问题

**Q: 启动后端报错端口8000被占用？**
```bash
netstat -ano | findstr :8000    # 查找占用进程PID
taskkill /PID <PID> /F          # 终止进程
```

**Q: QwQ-32B API Key 返回 403？**
确认使用 cucloud 平台的模型密钥，且 QWEN_BASE_URL 配置为 `https://aigw-nmhhht.cucloud.cn/v1`（不是 DashScope 官方地址）。Key 无效时系统自动降级为模板回复，其他功能不受影响。

**Q: HuggingFace 连接超时？**
系统已设置 `HF_HUB_OFFLINE=1`，使用本地缓存的嵌入模型。首次运行需联网下载 `text2vec-base-chinese`，可提前运行 `python scripts/download_model.py`。

**Q: 桌面端工单图片加载崩溃？**
图片加载使用 Pillow 解码缩放 + 临时文件方式，避免 PyQt6 6.11.0 在 Windows 下 QPixmap.scaled() 堆栈溢出问题。临时文件在应用启动时清理超过24小时的文件，退出时清空全部。

**Q: 提交客诉后前端显示"提交失败"但后端正常？**
AI Pipeline 需要多次调用大模型，总耗时可能超过60秒。确保 `api_client.py` 中 `submit_complaint` 的 timeout 设置为 120 秒。

**Q: 自动回复包含大模型思考过程？**
QwQ-32B 和 DeepSeek-V3 均为推理模型，输出包含 `<think.../think>` 标签的思考过程。`responder.py` 的 `_parse_response` 方法已自动剥离思考标签，只返回纯净回复。

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v1.0 | 2026-06 | 初始版本：4步Agent Pipeline、H5客诉提交、桌面端工单管理 |
| v1.1 | 2026-06 | 新增出单管理（5步Pipeline）、质量追溯、批量操作、升级转派 |
| v1.2 | 2026-06 | 删除出单模块，强化工单完整归档与质量追溯；Pipeline恢复4步；新增归档完整性校验；客户侧H5进度查询；企业生产侧批次/型号质量追溯 |

> v1.2 详细设计文档见 `docs/` 目录：PRD、架构设计文档、更新设计文档。

## License

MIT
