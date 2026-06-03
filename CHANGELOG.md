# CHANGELOG

> 面向阶段 / 发布的变更摘要，记录“项目能力变成了什么”。过程流水仍看 [开发日志](开发日志.md)，决策原因仍看 [PROJECT_PLAN.md](PROJECT_PLAN.md)。

## Unreleased

- 暂无未归档发布摘要。

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
