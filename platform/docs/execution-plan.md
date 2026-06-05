# 执行计划与技术栈

> 给**建平台的团队**看的：分几步做、用什么技术、目录怎么放、怎么交接给 AI 部署。
> 每完成一个 Phase 会更新本文件。

---

## 一、分阶段执行计划

> 严格按地基优先。Phase 0 不定死，后面全是返工。

- **Phase 0 — 地基：Schema + 契约**
  产出 [数据契约](schema.md) 与 [接入契约](contract.md) 的字段表、JSON Schema 校验定义、字段文档。这是后续一切的依据。

- **Phase 1 — 存储层（共享）**
  建 PostgreSQL 库与统一事件表（metadata 用 JSONB）、[工具注册表](registry.md)（**含门户展示字段**：category / display_name / description / icon / thumbnail / launch_url / sort_weight / enabled）、**用户账号表**（账号 / 密码哈希 / user_id / team_id / 角色）；建接入 API（接收一条流水 → 校验契约 → 落库）。三张表是两个前端共用的共享数据。

- **Phase 1.5 — 真实数据库冒烟**
  在不接真实工具的前提下，用真实 PostgreSQL 验证 `模拟 JSON → FastAPI /events → usage_event` 的落库链路。它只验证平台自身：建表 SQL、DB 连接、幂等、`ingested_at`、metadata JSONB。若本地无 Docker，可在具备 Docker 的机器上执行；未通过前不进入真实工具试点。

- **Phase 2 — 采集层 + 统一身份**
  a) **Phase 2A：参考 SDK + demo 工具**。SDK 是工具自报的便捷封装：自动生成 `record_id` / `conversation_id`，填 `schema_version`，支持异步上报、本地缓冲、重试队列、失败 / 超时也上报、token 归一化。demo 工具先验证 `demo_tool → SDK → /events → DB`，不接真实工具。
  b) **Phase 2B：统一 Auth API 最小版**。提供创建用户、登录、校验 token、`/auth/me`。入口来源分 `portal` / `direct` / `unknown`：从门户进入用短期 `launch_token`；直接打开工具时，工具可通过 SDK / Auth API 让用户使用同一账号登录；识别不了就 `anonymous`。本阶段先把 `entry_source` / `auth_method` 放进 `metadata`，暂不升 schema。
  c) **Phase 2C：真实工具低风险试点**。只选一个可改代码、低使用量、不影响生产的工具；记圈一 + token + status + duration + metadata 入口来源，`input_content` / `output_content` 原文可按需记录（已放开，决策 #34），跑一段时间看数据质量。
  d) **Phase 2D：本地转发服务**。转发请求给中转站 + 旁路记一条流水，供 OpenClaw / 黑盒工具改指向；它是兜底，不是所有流量必经总闸。形态取「透明代理为主 + 旁路记录兜底」两者都要。**设计稿见 [collection/relay/README.md](../collection/relay/README.md)（待确认后实现）**。

- **Phase 2.5 — 接入工程化（配合多方协作）**
  随真实工具试点暴露的协作摩擦补齐工具链，降低各团队自助接入的门槛：
  - **自助契约校验 CLI**（`tools/validate_payload.py`）：接入方在本地把自己构造的事件 JSON 喂给它，**离线**按 `shared/schema/event.schema.json` 校验合不合契约，当场报哪个字段不对。让「自行实现上报」（非用 SDK）的工具也能自检，减少接入来回。**待实现。**
  - **`tool_id` 发放通道**：✅ **已实现**（决策 #32）。`POST /registry/tools` 管理员 API（与 `/auth/users` 同门禁）把「登记 → 发 ID」从手工 `INSERT` 变成有鉴权、带命名校验、重复报 409 的端点；命名规则已定稿 `<team>-<tool>`（机器源 `backend/storage/registry.py` 的 `TOOL_ID_REGEX`）。实现：`backend/ingestion/app.py` `register_tool` + `backend/storage/registry.py`。通道细则见 [工具注册表 §三](registry.md)。
  - **接入层连接池**：当前 `backend/storage` 每请求新建 PostgreSQL 连接；真实工具放量前换连接池（如 `psycopg_pool`），避免并发上报时连接开销与耗尽。**待放量前实现（需联网装依赖）。**

- **Phase 3 — 分析层**
  基于原始流水计算四类结论（成本 / ROI / 采纳率 / 质量）。算式全部在此层，与采集解耦。

- **Phase 4 — 展示层（两个前端）**
  - **使用端 · 使用者门户**（`apps/user-portal`）：分类卡片、排序（偏好/频次/时间）、AI 工具推荐、登录入口（打开工具时注入 `user_id`）。详见 [使用端-工具门户](portal.md)。
  - **数据端 · 后台分析台**（`apps/admin-dashboard`）：明细查询 + 四类分析看板 + 接入管理页 + 账号管理。**后台看数据时可加一个「AI 数据分析」助手**（接 LLM API 对看板数据做自然语言分析）——**待定，需人工确认，后置实现**。

- **Phase 5 — 批量接入存量工具**
  在 Phase 2C 的真实工具试点稳定后，再批量接入。自写 / 可改代码的工具走自报（引 SDK 或自行上报，并接统一 Auth）；OpenClaw 改 base URL 指向转发服务；黑盒工具发独立 key 或走转发兜底。每个接入工具在 `integrations/` 下放一份接入适配/配置（工具本体仍各自独立部署，不进本仓库）。

---

## 二、建议的技术栈与目录结构

技术栈**已锁定**（详见 [代码规范](code-standards.md)，换栈需在决策记录立项）：

- 后端 / 接入 API / 分析层：Python 3.11+ + FastAPI + Pydantic v2
- 数据库：PostgreSQL（metadata = JSONB，天然适配自由口袋）
- 转发服务：默认 Python（httpx + SSE）；流式代理嫌费劲时可单独用 Node 实现这一个组件
- 校验：JSON Schema（`shared/schema/event.schema.json` 为唯一源，后端/前端模型均由它生成）
- 前端（两个）：React + Vite + TypeScript（图表用 Recharts / ECharts）
- 部署：docker-compose（局域网内一键起）

代码仓库目录结构（按「两个前端 + 共享后端 + 集成层」组织）：

```
platform/
├── README.md
├── docs/                        # 全部落地文档（SSOT 真源）：schema / contract / architecture / execution-plan / code-standards / registry / portal
├── shared/                      # 共享层：两端共用的数据与契约
│   ├── schema/event.schema.json #   机器可校验的 JSON Schema（唯一源，Phase 0）
│   ├── contracts/               #   由 schema 生成的 py/ts 模型（标「自动生成，勿手改」）
│   └── registry/                #   工具注册表定义/迁移（含门户展示字段）
├── backend/                     # 数据端共享后端
│   ├── ingestion/               #   接入 API（Phase 1）
│   ├── storage/migrations/      #   建表 SQL（事件表 + 注册表 + 用户账号表，Phase 1）
│   ├── analytics/               #   分析层（Phase 3）
│   └── auth/                    #   账号体系（Phase 1）
├── collection/                  # 采集层
│   ├── sdk/                     #   参考 SDK（Phase 2A）
│   └── relay/                   #   本地转发服务（Phase 2D，设计稿待确认）
├── integrations/                # 「存放各个工具」：每个工具一子目录（接入适配/配置）
│   └── _template/               #   接入模板（新工具照抄）
├── apps/                        # 两个前端
│   ├── user-portal/             #   使用端 · 使用者门户（Phase 4）
│   └── admin-dashboard/         #   数据端 · 后台分析台（Phase 4）
└── docker-compose.yml
```

> **当前进度（Phase 2A/2B 最小实现已完成，Phase 2C 已有试点模板）**：`platform/` 已产出 Phase 0 地基，打通 Phase 1 最小后端闭环，并新增真实数据库冒烟脚本、参考 SDK、demo 工具、统一 Auth API 最小版与真实工具试点模板。**Phase 1.5 真实 PostgreSQL 冒烟已在本机通过**（免安装 PG16 + uvicorn 起的真实服务，`模拟JSON → /events → usage_event`）；已登记首个真实工具 `aird-report`，工具侧 SDK 接入进行中（Phase 2C）。
> **SSOT 已全部转移到 `platform/docs/`**：原 `规划/` 目录（数据契约 / 接入契约 / 架构与原则 / 执行计划 / 代码规范 / 工具注册表 / 工具门户）已**全部搬入本目录并退役**。此后所有规范只改 `platform/docs/`，不再有「部分冻结」的双轨状态（见 [CLAUDE.md](../../CLAUDE.md) §1）。
> **下一步 = 执行真实数据库冒烟 + Phase 2C 真实工具试点验证**，交接命令见 §三。

---

## 三、交接命令（可直接粘贴给 AI 执行）

> **Phase 2A/2B 最小实现已完成**（见 §二「当前进度」与 [开发日志](../../开发日志.md)）。下面是 **真实数据库冒烟 + Phase 2C 真实工具试点验证** 的交接命令，可直接整段粘贴给执行 AI。
>
> ✅ **读单已简化**：SSOT 已全部在 `platform/`，规划目录退役。读 `platform/docs/` + 根目录治理文档即可，不必再区分「规划 vs platform」。

```
你要接续一个已完成 Phase 2A/2B 最小实现的项目，先执行真实数据库冒烟，再进入 Phase 2C 真实工具低风险试点验证。先按顺序读全这些，再动手：

【必读 —— 工程治理与现状】
- 根目录 CLAUDE.md（最高优先级：文档维护守则、SSOT 全在 platform/、改完自检清单）
- PROJECT_PLAN.md（决策记录，尤其 #1–#6、#13、#14、#26、#30；文档地图）
- 开发日志.md（最近几条 = Phase 1/2A/2B 做了什么 + 规划目录退役）
- CHANGELOG.md（阶段级能力摘要）

【必读 —— 规范与契约（SSOT 真源，全在 platform/docs/）】
- platform/docs/architecture.md         ← 架构与原则
- platform/docs/execution-plan.md        ← 本文件
- platform/docs/code-standards.md        ← 代码规范（写代码前必读）
- platform/docs/schema.md + platform/shared/schema/event.schema.json  ← 数据契约真源（v0.2）
- platform/docs/contract.md              ← 接入契约真源
- platform/docs/registry.md              ← 工具注册表
- platform/docs/portal.md                ← 使用端门户规划

【必读 —— 现有代码】
- platform/README.md、platform/backend/ingestion/app.py、platform/backend/storage/events.py、platform/backend/auth/*、platform/collection/sdk/*、platform/integrations/_template/*、platform/tools/smoke_db.py、platform/tools/seed_admin.py、platform/docs/smoke.md、platform/backend/storage/migrations/0001_init.sql、platform/pyproject.toml、platform/.env.example

【本轮要做 —— 真实 DB 冒烟 + Phase 2C】
1. 真实 DB 冒烟：
   - 用真实 PostgreSQL 验证 `模拟 JSON → POST /events → usage_event`；
   - 使用 platform/tools/smoke_db.py 与 platform/docs/smoke.md；
   - 若当前机器无 Docker，则明确记录未执行原因，并在具备 Docker / PostgreSQL 的机器上补跑；
   - 不接真实工具。
2. Phase 2C 真实工具试点：
   - 选择一个低风险、可改代码、调用路径清楚的真实工具；
   - 复制 platform/integrations/_template 为该工具目录，填写配置与试点记录；
   - 使用 collection.sdk.PlatformTracker 或等价封装上报；
   - 记圈一 + token + status + duration + metadata 入口来源；input_content / output_content 原文按需记录（已放开，见 schema.md 敏感内容策略）；
   - 工具侧必须保留环境变量开关，支持关闭上报回滚。
3. 验证：
   - 验证 portal / direct / unknown 至少覆盖实际存在的入口；
   - 验证 token 存在时由平台解析身份，缺身份时仍 anonymous 入库；
   - 验证 record_id 幂等与 SDK buffer / retry；
   - 试点跑 1 天或至少 20 次调用后，再决定是否批量接入。
4. 测试 + 闸门：
   - ruff / mypy strict / vulture / import-linter / pytest 全绿。

【不要做】
- 不实现分析层四类算式（Phase 3）、两个前端（Phase 4）、批量接真实工具（Phase 5）。
- 不接真实中转站；不硬编码任何 Key/口令/中转站地址/LLM 地址（全走 .env）。
- 不把 entry_source 立刻加成事件主字段；先放 metadata，等验证稳定后再考虑 schema v0.3。
- 原文记录策略已放开（决策 #34，可记 input_content / output_content）；读取侧权限、ROI 价值信号、价格表仍「待定，需人工确认」，保持占位。
- 改数据契约要按 CLAUDE.md §3 四连动（升 schema_version + 决策记录 + event.schema.json + 建表 SQL + 重跑代码生成）。

【完成后】
- 列出新增/修改的文件清单（区分实质实现 vs 仍占位）。
- 跑一遍机器闸门并贴结果（ruff/mypy/vulture/import-linter/pytest 全绿才算完成；红了修，不许加忽略糊弄）。
- 按 CLAUDE.md 在 开发日志.md 追加一条；有新取舍写进 PROJECT_PLAN 决策记录。
```

---

## 四、本机运行（dev）

> 正式部署目标是 docker-compose（§二），但当前开发机用「免安装 PostgreSQL + dev-run 脚本」。本节是**本机怎么跑的唯一真相**，别再散在聊天/记忆里。

**前置**：`platform/.env` 已存在（从 `.env.example` 复制填值，**不入库**），其中含 `DATABASE_URL` / `AUTH_TOKEN_SECRET`；离线机器另填 `PLATFORM_PYTHON`（匹配 `.pydeps` 的解释器）与 `PG_BIN` / `PG_DATA`（免安装 PG 路径）。

```powershell
cd platform
.\scripts\serve.ps1 start     # 一条命令：自动起 PG（若没起）+ 探活 DB + 起接入 API
.\scripts\serve.ps1 status    # 看 API 状态
.\scripts\pg.ps1   status     # 单看 PostgreSQL 状态
.\scripts\serve.ps1 stop      # 停 API（不停 PG）
.\scripts\pg.ps1   stop       # 停 PG
```

- `serve.ps1 start` 会先调 `pg.ps1` 把 PG 带起来，再**真实探活 DB**（连不上当场报错、不假装起好），最后起 API 并探活 `/health`。
- **开机不会自动恢复**：免安装 PG 不是常驻服务。要开机自启，跑一次 `.\scripts\autostart.ps1 install`（登录时自动 `serve start`）；撤销用 `.\scripts\autostart.ps1 remove`。
- 验证整条链：`GET http://127.0.0.1:8000/health` 返回 `{"status":"ok"}`；`POST /events` 一条事件应 `202 inserted:true`。

---

## 五、已知非标准项 / 待收敛

当前为「能跑、可试点」的开发态，下列偏离**标准/可复现**目标，放量或交接前需收敛（撞到就办，不必一次清完）：

| 项 | 现状（非标准） | 目标 | 优先级 |
|---|---|---|---|
| 数据库部署 | 手动/脚本起的免安装 `D:\pg-portable` | docker-compose（§二）统一起，或把 PG 注册为 Windows 服务 | 中 |
| Python 依赖 | 无 `requirements`/锁文件；靠 `.pydeps` 离线塞包 + `.env` 指定解释器 | 出 `requirements.txt`/锁文件，标准 venv 可复现；`.pydeps` 仅作无网临时手段 | 中 |
| 真实 TCP 服务跑法 | 依赖 codex-runtime Py3.12 + `.pydeps`（本机特殊） | 标准解释器 + 依赖安装即可起 | 中 |
| 凭据/脚本散落 | `admin-cred.txt`、smoke 脚本在 `D:\pg-portable` | 凭据走密钥管理；脚本归仓库 | 低 |
| ~~迁移执行~~ | ✅ **已落地**：`tools/migrate.py` 幂等执行器 + `schema_migrations` 跟踪表（决策 #35）。逻辑在 `backend/storage/migrate.py`，用法见 [migrations/README](../backend/storage/migrations/README.md) | —— | 完成 |
| 连接池 | 每请求新开连接（已加连接超时兜底） | 放量前接 `psycopg_pool` | 放量前 |

> 这些原先只记在 AI 记忆里，现搬入仓库成为可追踪事实（呼应 CLAUDE.md「占位明确」）。
