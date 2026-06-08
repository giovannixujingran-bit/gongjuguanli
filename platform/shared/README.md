# shared —— 共享层（两端共用）

两个前端共用的同一套数据与契约。

| 子目录 | 职责 |
|---|---|
| `schema/` | `event.schema.json`：数据契约唯一源（Phase 0 生成，现为空） |
| `contracts/` | 由 schema **代码生成**的 Pydantic / TS 模型，标「自动生成，勿手改」 |
| `registry/` | 工具注册表定义与迁移（含门户展示字段），见 [工具注册表](../docs/registry-工具注册表.md) |

> 共享层是地基：改这里牵动两端，遵守 [代码规范 §三](../docs/code-standards-代码规范.md)「schema 是唯一源」。
