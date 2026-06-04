# CHANGELOG

> 面向阶段 / 发布的变更摘要，记录“项目能力变成了什么”。过程流水仍看 [开发日志](开发日志.md)，决策原因仍看 [PROJECT_PLAN.md](PROJECT_PLAN.md)。

## Unreleased

### Changed

- **文档结构统一（破坏性：路径变更）**：原 `规划/` 目录全量搬入 `platform/docs/` 并退役——架构与原则 → `architecture.md`、执行计划 → `execution-plan.md`、代码规范 → `code-standards.md`、工具注册表 → `registry.md`、工具门户 → `portal.md`（与已有 `schema.md` / `contract.md` 同处）。所有跨文档链接已重定向。此后规范只有一个 SSOT 位置 `platform/docs/`，不再有「部分冻结」双轨（决策 #30）。**外部若有指向旧 `规划/...` 路径的书签需更新。**
- **账号创建收紧**：`POST /auth/users` 现需 admin token（非 admin 403 / 无 token 401），堵住「局域网内任何人给自己开 admin」；首个 admin 由运维离线跑 `tools/seed_admin.py` 引导。这是读取侧权限（谁能看原文）的前置防线。
- **采集端重试改为自愈**：SDK 上报成功时会顺带自动重发积压在本地 buffer 里的记录（靠 `record_id` 幂等去重），不再需要接入方手动 `flush()` 才能补发；buffer 读写加锁防并发损坏。
- **契约版本单一来源**：`schema_version` 由 `platform/shared/schema_version.py` 统一提供（`CURRENT_SCHEMA_VERSION` / `SUPPORTED_SCHEMA_VERSIONS`），SDK 与冒烟脚本不再各自硬编码字面量；升版本只改一处。
- **接入层对未知契约版本告警**：收到平台尚未支持解析的 `schema_version` 时**仍照收**（守「不阻断入库」），但记一条告警日志，避免静默沉淀无法解析的数据。
- 接入模板 buffer 路径改为按工具隔离（含 `tool_id`），避免同机多工具共用同一 buffer 文件互相覆盖。

### Added

- 新增 Phase 1.5 真实数据库冒烟脚本与说明：`platform/tools/smoke_db.py`、`platform/docs/smoke.md`。
- 新增 Phase 2A 参考 SDK：事件构造、异步上报、本地缓冲、重试、token 归一化与 `entry_source` / `auth_method` metadata。
- 新增 demo 工具，可模拟 `portal` / `direct` / `unknown` 三种入口。
- 新增 Phase 2B 统一 Auth API 最小版：创建用户、登录、校验 token、`/auth/me`，并在 `/events` 中用合法 token 覆盖 payload 身份。
- 新增 Phase 2C 真实工具试点模板：试点准入、采集范围、验收、回滚和配置样例。
- **新增《接入指南》** `platform/docs/integration-guide.md`：给接入方的总入口（五步流程 + 最小示例 payload + 上报方式 + 边界），可直接发给外部团队照着改。字段/义务细则仍链 schema.md / contract.md（守 SSOT）。
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
