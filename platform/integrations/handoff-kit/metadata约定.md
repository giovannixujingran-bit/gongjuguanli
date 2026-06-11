<!-- 自动生成 by platform/tools/export_integration_kit.py —— 勿手改。源文件：platform/docs/metadata-conventions-metadata约定与字段治理.md。改源后重跑脚本重生成本包。 -->

# metadata 语义约定与字段治理

> 本文件是 **metadata 怎么记** 与 **字段三层治理 / 晋升流程** 的 SSOT。
> 主表字段（圈一/二/三）的定义见 [schema-数据契约.md](schema-数据契约.md)（机器源 [event.schema.json](../shared/schema/event.schema.json)）；
> `tool_id` / 注册表见 [registry-工具注册表.md](registry-工具注册表.md)。本文件不重复字段定义，只管「没预置的东西怎么记、怎么演进」。

---

## 一、字段三层模型

平台的字段分三层，**改动重量不同**：

| 层 | 是什么 | 谁定 | 改动 |
|---|---|---|---|
| **1. 主表统一字段**（圈一/二/三） | 所有工具通用、要横向比较的（耗时 / token / 成本 / 状态…） | 平台定 | **重**：改它＝改数据契约，升 `schema_version`（见 [schema-数据契约.md](schema-数据契约.md)） |
| **2. metadata 语义约定** | 反复出现的「种类」的**统一记法**（文本 / 图片 / 分段耗时…） | 平台定形状，接入方申请、平台给 | **轻**：只改本文档，**不升事件契约版本** |
| **3. 纯一次性 metadata** | 真·只此一家、没必要立约定的 | 工具自填（仍守下方打字规则） | 无 |

### 「要不要记」和「记在哪」是两件独立的事

- **要不要记** ＝ 它有没有用 / 有没有意义（平台说了算）。**与频率无关——只要有用就记，全都记。**
- **记在哪** ＝ 查询 / 分析的方便程度：
  - 高频、要天天横向比 → 放**主表列**（查得顺手）；
  - 低频 / 一次性、但有用 → 放 **metadata**（在 PostgreSQL JSONB 里**完整、持久、可查**）。
- **「不晋升」≠「不记录」**：留在 metadata 的东西照样完整保存、需要时查得出来。晋升只是给高频项做查询优化，**不是给低频项判死刑**。

---

## 二、打字规则（所有 metadata 都要守）

metadata **位置自由，但形状有规范**，否则将来无法分析、无法搬家：

- **key**：`snake_case`，含义自解释（用 `report_type` 不用 `t`）。
- **值**：用 JSON 基本类型或对象数组；**时间 / 速度一律 number（毫秒）**，不要字符串；同一字段**单位统一**。
- **二进制（图片 / 文件 / 视频）绝不入库**：只存**引用（URI / 路径）+ 元数据（数量 / 尺寸 / 格式）**。
- **原文 / 敏感文本走主字段**：`input_content` / `output_content`（现允许记录，受敏感内容策略约束，见 [schema-数据契约.md](schema-数据契约.md)），**不要塞进 metadata**。metadata 只放**指标**（如字数）。

---

## 三、约定库（初始几类，可扩）

接入方记下列种类时，**一律按这里的形状**，使不同工具的同类数据可聚合：

| 场景 | 统一记法（metadata 内） | 类型 / 规则 |
|---|---|---|
| **分段耗时** | `section_timings = [{ "name": "概述", "ms": 1200 }, …]` | `ms` 为 number（毫秒） |
| **通用产出物** | `outputs = [{ "type": "...", … }]` | `type` ∈ `text` / `image` / `file` / `audio` / `video` |
| **图片产出** | `outputs` 项 `{ "type": "image", "count": 3, "ref": "<URI/路径>", "width": 1024, "height": 768, "format": "png" }` | **不存二进制**，只存引用 + 尺寸 / 数量 / 格式 |
| **文件 / 下载产出** | `outputs` 项 `{ "type": "file", "count": 1, "ref": "<URI/路径>", "bytes": 20480, "format": "pdf" }` | 同上，存引用 + 大小 / 格式 |
| **文本产出** | 原文 → 主字段 `output_content`（允许记录，见敏感内容策略）；指标 → `output_chars`（number） | 原文走主字段，metadata 只放指标 |
| **分类维度** | `report_type = "季度财报"`（按工具语义命名 key） | string，可约定枚举 |
| **章节 / 段落类型** | `chapter_type = "cover"`（一次生成对应的章节/段落类别，如 `cover` / `pattern-*`） | string、`snake_case` 或工具内既有 typeId；同一工具内取值稳定，便于按章节聚合成功率 / 耗时 |
| **错误详情** | `error = { "code": "TIMEOUT", "message": "…" }` | `status` 为 `failed` / `timeout` 时补充；`message` 注意脱敏 |
| **测试 / 非生产流量** | `test = true`（连接测试 / 冒烟 / 手工诊断 POST 等**非真实使用**的流量） | boolean；**分析层默认排除**；真实使用不带此键或为 `false`。开发 / 接入期往 `/events` 发的验证事件一律打此标，避免污染指标 |
| **来源 IP（平台盖章）** | `source_ip = "192.168.1.23"` | string；**平台服务端在接入层自动盖**（同 `ingested_at`），溯源 / 排障用，**接入方不用填**（填了也会被平台观测值覆盖）。优先取 `X-Forwarded-For` 第一跳（relay 转发时带回工具真实 IP），否则为直连对端 IP。**只用于溯源、不做鉴权**（决策 #7） |

> 整体耗时不进 metadata——用主表现成的 `duration_ms`（圈一）。别重造已有字段。
>
> **生效日期**：`chapter_type` 约定 2026-06-04 起生效（首个登记方 aird-report）；`test` / `source_ip` 约定 2026-06-10 起生效（`test` 隔离测试流量、分析层默认过滤；`source_ip` 由平台服务端盖章，用于溯源）。其余为初始约定。

---

## 四、申请 / 扩展流程（没预置的东西怎么办）

```
接入方要记一个新东西
  → ① 先查本约定库有没有现成的种类   ── 有 → 照用（与其它工具一致）
  → ② 没有 → 找平台
        平台判断：
          (a) 给一条新的 metadata 约定   → 轻：在本文档第三节加一行 + 标生效日期，
                                            不升事件 schema_version，不阻断入库
          (b) 该字段会被多工具复用 / 要横向分析（见下方「信号」）
                                          → 重：提为主表列，走 schema 升版本流程
```

**触发「提为主表列」的信号（不是定期开会，是撞到就办）：**
- 同一类东西，**第 3 个工具**又来申请；
- 用 JSONB 对它**做分析很费劲**（聚合 / 对比频繁）。

平时接工具、做分析自然会撞上这些信号，撞上再提列即可。**没撞上就一直留 metadata，完整保存、不丢。**

---

## 五、晋升：metadata 字段 → 主表列

**好不好搬家，取决于 metadata 当初记得干不干净**——这正是第二节打字规则的长期价值。

步骤（以 `metadata.report_type` 提为列为例）：

1. 加列（PG 加可空列是秒级，不重写表）：`ALTER TABLE usage_event ADD COLUMN report_type TEXT;`
2. 回填历史：`UPDATE usage_event SET report_type = metadata->>'report_type' WHERE metadata ? 'report_type';`
3. 接入层把 `metadata.report_type` 自动落进新列；
4. 走数据契约四连动：升 `schema_version` + 改 [schema-数据契约.md](schema-数据契约.md) / [event.schema.json](../shared/schema/event.schema.json) / 建表 SQL + 在 [PROJECT_PLAN](../../PROJECT_PLAN.md) 决策记录记一条 + 重生成模型（见 [CLAUDE.md](../../CLAUDE.md) §3）。

注意事项：

- **对接入方透明**：平台从 metadata 映射进列，**老工具一行代码都不用改**，照旧发 metadata 也能进列；晋升是平台单方面可做的平滑操作，不必一次跨团队大改。
- **历史脏数据是最大风险**：metadata 无强类型，若当初没按约定记（类型漂移 / key 拼错 / 单位不一），回填要先清洗。**守约定 = 将来一行 `UPDATE` 搞定。**
- **历史行该列为 NULL**：约定存在之前的旧记录没这字段，列为 NULL 属正常（选填），分析时当「那时没记」处理。
- **大表回填**分批进行，避免长锁；内网量级一般无虞。

---

## 六、待定

- **metadata 形状校验告警**：metadata 不符合本文约定（类型 / 必需 key）时，是否在接入层**记一条告警日志（仍照收、不拒收，守「不阻断入库」）**——**待定，需人工确认**。
- **敏感内容策略读取侧**：`input_content` / `output_content` 原文记录已放开（决策 #34）；仅**读取侧可见范围**（多用户上看板后谁能看原文）+ **留存策略**仍**待定，需人工确认**（见 [schema-数据契约.md](schema-数据契约.md)）。
