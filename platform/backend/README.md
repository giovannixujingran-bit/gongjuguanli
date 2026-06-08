# backend —— 数据端共享后端

采集之上、展示之下的服务层。对应五层架构的 2/3/4 层（见 [架构与原则](../docs/architecture-架构与原则.md)）。

| 子目录 | 职责 | Phase |
|---|---|---|
| `ingestion/` | 接入 API：收一条流水 → 校验契约 → 落库 | 1 |
| `storage/migrations/` | 建表 SQL：事件表 + 工具注册表 + 用户账号表（JSONB） | 1 |
| `analytics/` | 分析层：成本 / ROI / 采纳率 / 质量，算式纯函数 | 3 |
| `auth/` | 账号体系：账号 / 密码哈希 / user_id / 角色 | 1 |

> 单向依赖、算式后置见 [代码规范](../docs/code-standards-代码规范.md) §二、§六。
