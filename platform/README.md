# 内部工具汇总与分析平台 —— platform（代码区）

> 公司局域网内的统一中枢平台：把各类工具（自写 / 开源自部署 / 黑盒）的**每一次使用**汇总记录，
> 在统一数据契约之上做**成本 / ROI / 使用率 / 质量**四类分析。
> 本目录是代码区，所有规范文档都在 `docs/`。

## 当前状态

**Phase 1 已打通最小后端闭环，Phase 2A/2B 已进入最小实现**：在 Phase 0 地基上，
已生成契约模型，实现统一上报 API、`record_id` 幂等、服务端 `ingested_at`、匿名用户兜底、
PostgreSQL 落库实现与模拟数据测试；并新增真实数据库冒烟脚本、参考 SDK、demo 工具、
统一 Auth API 最小版和真实工具试点模板。
转发 / 分析层 / 两个前端仍为占位，留待 Phase 2D+。
**SSOT 状态**：全部规范文档已统一在 `docs/`（schema / contract / architecture / execution-plan / code-standards / registry / portal），原 `规划/` 目录已退役（决策 #26 → #30）。

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

## 三种采集手段（按对工具的控制权决定，与开/闭源无关）

| 你对它的控制权 | 采集手段 | 数据粒度 |
|---|---|---|
| 能改**代码** | **工具自报**（触发点直接上报，SDK 为便捷封装，主路） | 最全：token + 工具 + 用户 + 团队 + 结果 |
| 改不了 / 不想改代码，但能改**接口地址（base URL）** | 改 base URL 指向本地转发服务，平台旁路代采（不想 fork 的开源、可配 endpoint 的闭源都适用） | token + 工具；用户粒度看透传 |
| 连地址都改不了，但能定它用**哪把 API Key** | 独立 API Key 区分到工具（供应商按 key 报量） | 通常只到「哪个工具」 |

无论哪种，最终都按同一 schema 落库；差异由弹性选填字段与 `metadata` 自由区吸收。详见 [架构 §四](docs/architecture-架构与原则.md)。

---

## 目录

| 目录 | 职责 | 当前产出 |
|---|---|---|
| `docs/` | 落地文档（承接 SSOT） | ✅ [schema-数据契约.md](docs/schema-数据契约.md)、[contract-接入契约.md](docs/contract-接入契约.md) |
| `shared/schema/` | 机器可校验 JSON Schema（唯一源） | ✅ [event.schema.json](shared/schema/event.schema.json) |
| `shared/contracts/` | 由 schema 生成的 py/ts 模型（标「自动生成，勿手改」） | ✅ `event_model.py`、`event.d.ts` |
| `shared/registry/` | 工具注册表定义/迁移 | 表见 `backend/storage/migrations/` |
| `backend/storage/migrations/` | 建表 SQL（事件表 + 注册表 + 账号表） | ✅ [0001_init.sql](backend/storage/migrations/0001_init.sql) |
| `backend/ingestion/` | 接入 API（收一条流水 → 校验 → 落库） | ✅ `/events`、`/health`、Auth token 身份覆盖、模拟数据测试 |
| `backend/analytics/` | 分析层（四类结论的纯函数） | 占位（Phase 3） |
| `backend/auth/` | 账号体系 | ✅ PBKDF2 密码哈希、创建用户、登录、校验 token、`/auth/me` |
| `collection/sdk/` | 参考 SDK | ✅ 事件构造、异步上报、本地缓冲、重试、token 归一化、demo |
| `collection/relay/` | 本地转发服务 | 占位（Phase 2D） |
| `integrations/` | 各接入工具的适配/配置（工具本体不在此） | ✅ 真实工具试点模板；未接真实工具 |
| `apps/user-portal/` `apps/admin-dashboard/` | 两个前端 | 占位（Phase 4） |

## 本地起库

```
docker-compose up   # PostgreSQL + 接入 API + 两前端占位
```

配置/密钥（`DATABASE_URL`、`AUTH_TOKEN_SECRET`、中转站地址、API Key、DB 口令、LLM 地址）
**一律走环境变量**，代码与镜像里零硬编码。
