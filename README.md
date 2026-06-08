# 内部工具汇总与分析平台

公司局域网内的统一平台：把各类工具（自写 / 开源自部署 / 黑盒）的**每一次使用**汇总记录，在统一数据契约之上做**成本 / ROI / 使用率 / 质量**四类分析。由**两个前端（使用端·使用者门户 / 数据端·后台分析台）+ 共享后端**组成。

> **当前版本：v0.0.1** ｜ 阶段：Phase 2A/2B 最小实现已完成，下一步真实数据库冒烟 + Phase 2C 真实工具试点。

## 从哪读起

| 想了解 | 看这里 |
|---|---|
| **怎么维护这套文档（先读）** | [CLAUDE.md](CLAUDE.md) —— 维护守则 + SSOT 规则 + 远程仓库与版本发布规范 |
| 项目总纲 / 文档地图 / 决策记录 | [PROJECT_PLAN.md](PROJECT_PLAN.md) |
| 规范文档（架构 / 契约 / 代码规范 / 接入…） | [platform/docs/](platform/docs/) |
| 能力变更摘要 | [CHANGELOG.md](CHANGELOG.md) ｜ 过程流水 [开发日志.md](开发日志.md) |
| 代码 | [platform/](platform/)（共享后端 + 采集层 + 集成层；两个前端占位） |

## 技术栈

后端 Python 3.11+ / FastAPI / Pydantic v2 ｜ PostgreSQL（metadata=JSONB）｜ 前端 React + Vite + TypeScript ｜ 部署 docker-compose。数据契约唯一源 [event.schema.json](platform/shared/schema/event.schema.json) 生成各层模型。

## 版本

版本号与发版规范见 [CLAUDE.md「远程仓库与版本发布」](CLAUDE.md)。SemVer，tag 形如 `vX.Y.Z`，每个 tag 对应 [CHANGELOG](CHANGELOG.md) 的一个发布块。**注意仓库版本号 ≠ 事件数据契约 `schema_version`**（后者见 [schema-数据契约.md](platform/docs/schema-数据契约.md)）。
