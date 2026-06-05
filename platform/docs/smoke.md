# Phase 1.5 真实数据库冒烟

目标：只验证平台自身链路，不接真实工具。

```
模拟 JSON -> POST /events -> usage_event
```

## 前置条件

- PostgreSQL 已执行 `backend/storage/migrations/0001_init.sql`。
- 接入 API 已启动，默认地址 `http://127.0.0.1:8000/events`。
- 环境变量里有真实 `DATABASE_URL`。

> 本机 dev 可一条命令满足后两条：`cd platform; .\scripts\serve.ps1 start`（自动起 PG + 探活 DB + 起 API）。完整本机运行说明见 [execution-plan.md](execution-plan.md) §四。

## 运行

```powershell
cd platform
$env:DATABASE_URL="postgresql://platform:change-me-in-real-env@127.0.0.1:5432/platform"
$env:INGESTION_API_URL="http://127.0.0.1:8000/events"
python tools/smoke_db.py
```

成功时会打印写入的 `record_id`、`tool_id`、`user_id` 与 `metadata`。

## 说明

- 本脚本使用 `tool_id = smoke-demo-tool`，`user_id = anonymous`。
- `metadata.entry_source = unknown`，因为它不是从门户或真实工具进入。
- 如果当前机器没有 Docker / PostgreSQL，只保留脚本；到有数据库的机器上执行。
