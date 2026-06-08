# handoff-kit —— 接入资料分发包（自动生成，勿手改）

本目录由 `platform/tools/export_integration_kit.py` 从 SSOT 文档生成，供没有仓库访问权的
接入方直接获取（整个文件夹发给对方即可）。

- **不要手改本目录任何文件**：改 `docs/integration-guide-接入指南.md` /
  `docs/contract-接入契约.md` / `docs/schema-数据契约.md` /
  `shared/schema/event.schema.json` 等源文件后，重跑生成脚本：
  `python tools/export_integration_kit.py`（详见 CLAUDE.md §3 改动传播规则）。
- 本目录不是 SSOT，只是上述文档的分发副本。
