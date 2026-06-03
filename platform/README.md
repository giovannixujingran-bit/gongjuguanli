# 内部工具汇总与分析平台 —— platform（代码区）

> 公司局域网内的统一中枢平台：把各类工具（自写 / 开源自部署 / 黑盒）的**每一次使用**汇总记录，
> 在统一数据契约之上做**成本 / ROI / 使用率 / 质量**四类分析。
> 本目录是代码区，与规划文档 `../规划/` 平级。

## 当前状态

**Phase 0 已落地**：数据契约、JSON Schema、建表 SQL、落地文档、脚手架配置已产出（见下「目录」）。
业务逻辑（SDK / 转发 / 分析层 / 两个前端）仍为占位，留待 Phase 2+。
**SSOT 状态**：数据契约 / 接入契约已有本目录对应物（`docs/` + `shared/schema/`）；其余规范（架构 / 执行计划 / 代码规范 / 工具注册表 / 工具门户）仍以 `../规划/` 为准。`规划/` 的冻结方式**待人工确认**（见 [PROJECT_PLAN 决策 #26](../PROJECT_PLAN.md)）。

---

## 项目目标

记录每一次工具使用，产出四类分析结论：① 成本与 token 消耗 ② 效率与投入产出（ROI）③ 使用率与采纳情况 ④ 结果质量评估。

## 三条核心原则

1. **数据契约统一，接入方式可变。** 不强求工具长得一样，只强求落库记录格式一样（统一 schema）。
2. **采集端只记原始事实，计算一律后置。** 采集端只诚实记录「发生了什么」；所有会变的算式放分析层。
3. **采集点放在可长期掌控的那一层。** 绝不把采集逻辑写在随时会换的第三方中转站上——放在自己的 SDK 或自建转发服务里。

## 五层架构

```
5. 展示层  两个并列前端（共用下面同一套后端）
   · 使用端 · 使用者门户：分类卡片 · 排序 · AI 推荐 · 登录入口
   · 数据端 · 后台分析台：明细查询 · 四类看板 · 接入/账号管理
4. 分析层  Analytics —— 成本 · ROI · 采纳率 · 质量（所有算式在此，可随时改）
3. 存储层  Storage —— 统一事件表 · 工具注册表 · 用户账号表（PostgreSQL，metadata 用 JSONB）
2. 接入层  Ingestion —— 统一上报 API + 进入即自动校验契约
1. 采集层  Collection —— ① 工具自报（主路）② 本地转发服务 ③ 独立 API Key
```

两个前端只通过共享后端的数据相连，**互不调用**。依赖只能自下而上单向流。

## 三类工具的接入方式

| 类别 | 采集手段 | 数据粒度 |
|---|---|---|
| 自写 / 可改代码 | **工具自报**（触发点直接上报，SDK 为便捷封装，主路） | 最全：token + 工具 + 用户 + 团队 + 结果 |
| 开源自部署（如 OpenClaw） | 改 base URL 指向本地转发服务，平台旁路代采 | token + 工具；用户粒度看透传 |
| 纯黑盒现成 | 独立 API Key 区分，或走转发服务兜底 | 通常只到「哪个工具」 |

无论哪种，最终都按同一 schema 落库；差异由弹性选填字段与 `metadata` 自由区吸收。

---

## 目录

| 目录 | 职责 | Phase 0 产出 |
|---|---|---|
| `docs/` | 落地文档（承接 SSOT） | ✅ [schema.md](docs/schema.md)、[contract.md](docs/contract.md) |
| `shared/schema/` | 机器可校验 JSON Schema（唯一源） | ✅ [event.schema.json](shared/schema/event.schema.json) |
| `shared/contracts/` | 由 schema 生成的 py/ts 模型（标「自动生成，勿手改」） | 生成命令已备（见根 README/配置） |
| `shared/registry/` | 工具注册表定义/迁移 | 表见 `backend/storage/migrations/` |
| `backend/storage/migrations/` | 建表 SQL（事件表 + 注册表 + 账号表） | ✅ [0001_init.sql](backend/storage/migrations/0001_init.sql) |
| `backend/ingestion/` | 接入 API（收一条流水 → 校验 → 落库） | 占位（Phase 1） |
| `backend/analytics/` | 分析层（四类结论的纯函数） | 占位（Phase 3） |
| `backend/auth/` | 账号体系 | 占位（Phase 1） |
| `collection/sdk/` `collection/relay/` | 参考 SDK + 本地转发服务 | 占位（Phase 2） |
| `integrations/` | 各接入工具的适配/配置（工具本体不在此） | 占位（Phase 5） |
| `apps/user-portal/` `apps/admin-dashboard/` | 两个前端 | 占位（Phase 4） |

## 本地起库（脚手架）

```
docker-compose up   # PostgreSQL + 接入 API 占位 + 两前端占位（服务内部逻辑留空）
```

配置/密钥（中转站地址、API Key、DB 口令、LLM 地址）**一律走环境变量**，代码与镜像里零硬编码。
