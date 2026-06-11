# CHANGELOG

> 面向阶段 / 发布的变更摘要，记录“项目能力变成了什么”。过程流水仍看 [开发日志](开发日志.md)，决策原因仍看 [PROJECT_PLAN.md](PROJECT_PLAN.md)。
> 版本号与发版规范见 [CLAUDE.md「远程仓库与版本发布」](CLAUDE.md)。

## Unreleased

### Added

- **事件来源 IP 溯源（决策 #41）**：接入层收 `/events` 时由平台**服务端自动盖** `metadata.source_ip`（同 `ingested_at` 的服务端盖章），用于「某条记录是哪台机器发来的」的溯源 / 排障。优先取 `X-Forwarded-For` 第一跳（为 Phase 2D relay 预留，转发时带回工具真实 IP），否则用直连对端 IP。**进 metadata、不升 `schema_version`**；只溯源、不做鉴权（不违反决策 #7）。接入方无需改动。

## v0.2.0 — 2026-06-09

### Added

- **钉钉组织同步（Phase A 钉钉打通，决策 #38/#39）**：新增 `backend/org_sync`，从钉钉拉取部门树 + 人员并落平台库（新增 `department` 表、`user_account.dingtalk_userid` + `display_name`、`user_department` 关系表，迁移 `0002`–`0004`）。钉钉接口用仓库已有的 `httpx` 直调经典通讯录 topapi（`gettoken` / `department/listsub` / `user/listid` / `user/get`），藏在 `DingtalkClient` 抽象后（`HttpxDingtalkClient` 实现 + token 缓存）；官方新 SDK 不覆盖部门树遍历，故不用 SDK（决策 #39）。同步命令 `tools/sync_dingtalk.py`（需 `DATABASE_URL` / `DINGTALK_CLIENT_ID` / `DINGTALK_CLIENT_SECRET`）。**已在真实钉钉企业 + 本机 PostgreSQL 16 端到端验证**：拉真实 6 人 + 部门落库、二次重跑幂等、全套机器闸门绿。
- **设计稿《钉钉组织同步与部门化工具治理》**：`platform/docs/dingtalk-钉钉组织与部门治理/`（4 份分册 + 钉钉态登录流程图 SVG）。原待定项 T1–T6 已人工拍定为 P1–P6（同步频率每小时+手动、密码退役、新员工即时拉、白名单关联表、内网 PC、软删保留）。**员工免登端点与 Phase B 部门化可见性治理仍为设计稿、待实现。**
- **Smart Tool Hub 高保真 mockup**：新增 `platform/docs/mockups/stitch_smart_tool_hub/` 设计说明、单页 `code.html`、截图与 zip 包，并将原 `presentation/index.html` 重命名为 `presentation/项目总览.html`，便于把内部项目总览与门户视觉参考分开管理。

### Changed

- **账号体系：密码登录退役第一步（决策 #38/P2）**：`user_account.password_hash` 改为可空（钉钉免登账号无密码）；`UserAccount.password_hash` 类型改 `str | None`，密码登录对无密码账号直接拒绝。事件契约不变、不升 `schema_version`。

## v0.1.0 — 2026-06-08

> 自 v0.0.1 起的累积：新增「AI 接入向导」接入能力、`platform/docs/` 规范文档统一改名（破坏性路径变更）、采集手段表述订正，并新增内部架构说明文档。

### Added

- **AI 接入问诊向导**：新增 `platform/docs/ai-intake-guide-AI接入向导.md`——给接入方的 AI 看的接入剧本（决策树自助判定字段、只在业务判断处反问工具方、产出接入配置 + 方案；最高原则「只接数据、不影响原工具」）。已纳入 `tools/export_integration_kit.py` 分发包（handoff-kit 多一份「AI接入向导.md」）、文档地图与 CLAUDE.md §1。
- **内部架构说明文档** `presentation/index.html`：可滚动的「可视化 README」，含架构数据流图、运行/部署流程图、以三原则贯穿的叙事主线；供自留档 / 汇报多用（设计稿 `presentation/DESIGN.md`）。

### Changed

- **`platform/docs/` 规范文档统一改名为「英文-中文.md」（破坏性：路径变更）**：`architecture.md` → `architecture-架构与原则.md`、`schema.md` → `schema-数据契约.md`、`smoke.md` → `smoke-数据库冒烟.md` 等 11 份；文件名一眼可读、`git mv` 保留历史。全仓库引用（PROJECT_PLAN / CLAUDE / 各 README / docs 互链 / CI / pre-commit / pyproject / 多个 `.py` 注释 / `event.schema.json` 注释）已同步重定向，handoff-kit 已重生成（决策 #36）。**外部若有指向旧路径（如 `platform/docs/architecture.md`）的书签需更新。**
- **采集手段表述订正：由「按工具来源」改为「按控制权」（决策 #37）**：原架构第四节把「开源自部署（例 OpenClaw）」绑定到「改不动代码、只能转发」，属事实错误（OpenClaw 完全开源、代码可改）。订正为按「能否 / 愿否改代码」三道能力闸门判定（改代码 → 自报 / 改 base URL → 转发 / 配 key → 独立 key），并写明「开 / 闭源不是判定依据」——闭源能配 endpoint 照样转发、开源不愿 fork 也走转发。连带改 `architecture-架构与原则.md` / `collection/relay/README.md` / `contract-接入契约.md` / `platform/README.md`。

### Removed

- 删除 `docs/superpowers/`（AI 接入向导的过时设计稿 / 实现计划——功能已落地、且不在本项目 SSOT 体系内）。

## v0.0.1 — 2026-06-05

> 首个发布。涵盖 Phase 0 地基 → Phase 1 存储/接入 → Phase 1.5 真实 DB 冒烟 → Phase 2A/2B 采集 SDK + 统一 Auth 最小版，并补齐数据库迁移执行器。下列条目为本版累计能力。

### Changed

- **文档结构统一（破坏性：路径变更）**：原 `规划/` 目录全量搬入 `platform/docs/` 并退役——架构与原则 → `architecture.md`、执行计划 → `execution-plan.md`、代码规范 → `code-standards.md`、工具注册表 → `registry.md`、工具门户 → `portal.md`（与已有 `schema.md` / `contract.md` 同处）。所有跨文档链接已重定向。此后规范只有一个 SSOT 位置 `platform/docs/`，不再有「部分冻结」双轨（决策 #30）。**外部若有指向旧 `规划/...` 路径的书签需更新。**
- **账号创建收紧**：`POST /auth/users` 现需 admin token（非 admin 403 / 无 token 401），堵住「局域网内任何人给自己开 admin」；首个 admin 由运维离线跑 `tools/seed_admin.py` 引导。这是读取侧权限（谁能看原文）的前置防线。
- **采集端重试改为自愈**：SDK 上报成功时会顺带自动重发积压在本地 buffer 里的记录（靠 `record_id` 幂等去重），不再需要接入方手动 `flush()` 才能补发；buffer 读写加锁防并发损坏。
- **契约版本单一来源**：`schema_version` 由 `platform/shared/schema_version.py` 统一提供（`CURRENT_SCHEMA_VERSION` / `SUPPORTED_SCHEMA_VERSIONS`），SDK 与冒烟脚本不再各自硬编码字面量；升版本只改一处。
- **接入层对未知契约版本告警**：收到平台尚未支持解析的 `schema_version` 时**仍照收**（守「不阻断入库」），但记一条告警日志，避免静默沉淀无法解析的数据。
- 接入模板 buffer 路径改为按工具隔离（含 `tool_id`），避免同机多工具共用同一 buffer 文件互相覆盖。
- **放开原文记录（影响接入做法）**：原「首轮不记原文」取消，`input_content` / `output_content` 现可按需上报，写入侧不设门禁（内网、唯一接入方为平台方本人，决策 #34）。仅**读取侧可见范围**（多用户上看板谁能看原文）与**留存策略**仍待定、留占位。接入方不再被要求屏蔽原文；试点模板、接入指南、字段文档、metadata 约定同步更新。
- **DB 连接加超时（健壮性）**：所有仓库经统一入口 `backend/storage/db.connect` 连接，带 `connect_timeout`（默认 5s，`DB_CONNECT_TIMEOUT` 可覆盖）。PostgreSQL 不可达时**快速失败返回 500**，不再无限挂起——此前 PG 未启动会导致 `POST /events` 卡死、并可能拖垮请求线程池连带 `/health` 假死。

### Added

- **新增数据库迁移执行器**（影响部署/升级方式）：`tools/migrate.py` 幂等地按编号顺序应用 `backend/storage/migrations/*.sql`，靠 `schema_migrations` 跟踪表记「哪些办过了」、只跑没办过的，每张迁移连同登记同事务。补上了原先「`0001` 只在 docker 首次空库时执行、`0002+` 永不自动生效」的缺口——这是平台「schema 可演进」设计能真正落到库上的前提（决策 #35）。旧库需先基线、全新库直接跑，用法见 `backend/storage/migrations/README.md`。已在本机 PostgreSQL 真库验证（应用 / 幂等重跑 / 多语句 / ALTER）。`scripts/serve.ps1 start` 已接入：起 API 前自动应用迁移（幂等、失败即抛），本机起服务即自动跟上库结构。
- **本机运行脚本**：`scripts/pg.ps1`（启停免安装 PostgreSQL）、升级 `scripts/serve.ps1`（`start` 时自动拉起 PG + **真实探活 DB**，连不上当场报错而非假装起好）、`scripts/autostart.ps1`（注册「登录自启」计划任务，一键 install/remove）。本机运行说明与「已知非标准项 / 待收敛」清单写入 `docs/execution-plan.md` §四 / §五。
- 新增 Phase 1.5 真实数据库冒烟脚本与说明：`platform/tools/smoke_db.py`、`platform/docs/smoke.md`。
- 新增 Phase 2A 参考 SDK：事件构造、异步上报、本地缓冲、重试、token 归一化与 `entry_source` / `auth_method` metadata。
- 新增 demo 工具，可模拟 `portal` / `direct` / `unknown` 三种入口。
- 新增 Phase 2B 统一 Auth API 最小版：创建用户、登录、校验 token、`/auth/me`，并在 `/events` 中用合法 token 覆盖 payload 身份。
- 新增 Phase 2C 真实工具试点模板：试点准入、采集范围、验收、回滚和配置样例。
- **新增《接入指南》** `platform/docs/integration-guide.md`：给接入方的总入口（五步流程 + 最小示例 payload + 上报方式 + 边界），可直接发给外部团队照着改。字段/义务细则仍链 schema.md / contract.md（守 SSOT）。
- **新增《metadata 语义约定与字段治理》** `platform/docs/metadata-conventions.md`：定字段三层模型（主表统一字段 / metadata 约定 / 一次性）、metadata 打字规则与约定库（文本/图片/分段耗时等统一记法）、没预置字段的申请扩展流程、metadata→主表列的晋升步骤。明确「有用就全记、频率只决定记在哪、不晋升≠不记录」。决策 #33。
- **新增接入资料分发包生成器** `platform/tools/export_integration_kit.py`：从接入文档生成可直接发给无仓库访问权接入方的 `platform/integrations/handoff-kit/`（指南 + 契约 + 字段文档 + event.schema.json + 说明）。改接入文档后重跑即同步，分发包非 SSOT、勿手改（规范见 CLAUDE.md §3）。
- **新增 `tool_id` 发放通道**：管理员 API `POST /registry/tools`（需 admin token，与 `/auth/users` 同门禁）。同事接入第一步——领 `tool_id`——从此有正式入口：带命名校验（`<team>-<tool>`，非法 422）、重复登记 409、落 `tool_registry`。命名规则定稿（决策 #32），机器源 `backend/storage/registry.py` 的 `TOOL_ID_REGEX`。已在本机 PostgreSQL 16 真库验证（注册 / 重复 / 非法 / 鉴权四态）。

### Planned

- **Phase 2.5 接入工程化**剩余项：自助契约校验 CLI（`tools/validate_payload.py`）、接入层连接池（`psycopg_pool`）。（`tool_id` 发放通道已完成，见上方 Added。）
- 本地转发服务（relay）兜底通道：设计待与负责人确认后实现（Phase 2D）。
- 真实 DB 冒烟的 **TCP 服务（uvicorn）那一跳**：本机无 uvicorn + PyPI 受限暂跑不了，到能联网 / 有 uvicorn 的机器按 `smoke.md` 补跑（落库链路本身已在本机用进程内 ASGI + 真库验证通过）。
- 选择一个低风险、可改代码的真实工具做 Phase 2C 试点。
- `entry_source` / `auth_method` 暂不升 schema；等 demo 和真实试点稳定后再评估 schema v0.3。

## 2026-06-03 — Phase 1 最小后端闭环

### Added

- 从 `platform/shared/schema/event.schema.json` 生成 Pydantic v2 模型与 TS 类型。
- 新增 FastAPI 接入 API：`GET /health`、`POST /events`。
- 新增模拟事件上报闭环：契约校验、圈一缺失拒收、`user_id` 缺失补 `anonymous`、服务端写入 `ingested_at`。
- 新增 `record_id` 幂等落库逻辑，PostgreSQL 使用 `INSERT ... ON CONFLICT DO NOTHING`。
- 新增账号密码哈希 / 校验内部函数，使用 PBKDF2-SHA256，不存明文。
- 新增后端测试覆盖：模拟上报成功、缺必填拒收、重复上报幂等、密码哈希、存储参数转换。

### Changed

- 后端机器闸门进入 Phase 1 严格档：ruff、mypy strict、vulture、import-linter、pytest 必过；前端仍为占位宽松档。
- schema 代码生成由外部 `datamodel-code-generator` / `json-schema-to-typescript` 改为仓库内本地生成器 `platform/tools/generate_contracts.py`。

### Not Included

- 未接真实工具。
- 未实现采集 SDK / relay。
- 未实现分析层与两个前端业务。
- 未替用户决定敏感内容策略、读取侧权限、ROI 价值信号、价格表。

## 2026-06-03 — Phase 0 地基

### Added

- 建立 `platform/` 代码区骨架。
- 落地数据契约 v0.2：`platform/docs/schema.md` 与 `platform/shared/schema/event.schema.json`。
- 落地接入契约：`platform/docs/contract.md`。
- 新增初始建表 SQL：统一事件表、工具注册表、用户账号表。
- 新增 docker-compose 骨架、`.env.example`、后端 / 前端机器闸门配置骨架。

### Changed

- 数据契约与接入契约从 `规划/` 部分冻结，SSOT 转移至 `platform/`。

### Not Included

- 未实现业务逻辑。
- 未接真实工具或真实中转站。
