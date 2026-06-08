# 接入指南 —— 给接入方的总入口（照着做即可）

> **一句话**：把你工具的**每一次使用**，在使用结束时拼成一条统一格式的 JSON，POST 给平台的接入 API。怎么采、用什么语言不限，只要那条记录格式对。
>
> 本指南是**快速上手的总入口**：给步骤、给最小示例、给边界。字段与义务的**完整定义**链到对应文档（不在本文重复，避免不一致）。

---

## 你和平台的分工（先看这个，别多做）

你只需要做**一件事**：在工具的调用/触发点，**把每次使用上报一条记录**。其余都在平台侧，**不要在你那边重复建设**：

| 这些**平台已经做了**，你不用建 | 你要做的 |
|---|---|
| ❌ 用户/账号管理（身份来自平台） | ✅ 上报时带上平台给的身份，或记 `anonymous` |
| ❌ 使用统计 / 分析看板 | ✅ 只管上报，统计平台来做 |
| ❌ 工具目录 / 注册表 | ✅ 找平台领一个 `tool_id` 即可 |

- **人员不用同步名单**：身份的唯一来源是平台账号体系。首轮记 `anonymous`（不用管人）；以后要按真人统计，也是「平台门户注入 `user_id`」或「你接平台 Auth 让用户用**平台账号**登录」，**不是把你那边的用户表导给平台**。
- **不必自建管理系统**：平台就是那个统一系统（管工具、管人、收数据、出分析、做入口）。各工具各建一套，正好破坏"统一汇总、横向可比"的初衷。
- **例外**：你工具若**本来就有**自己的登录/用户系统，自用保留无妨；但对接平台是「复用 / 对接平台身份」，不是为平台**新建**一套。

> 一句话：**你只上报，平台负责管理与分析。**

---

## 0. 先确认你适用（当前阶段边界）

| 适用 | 暂不适用 |
|---|---|
| ✅ **能改代码**的工具（在调用/触发点加一段上报） | ❌ 改不了代码的黑盒工具（兜底 relay 属 Phase 2D，暂未提供） |
| ✅ 记「圈一事实 + token + 状态 + 耗时 + 入口来源」，需要的话连同 `input_content`/`output_content` 原文一起记 | —— |

不确定自己属于哪类，先找平台方确认。原文记录已放开（读取侧谁能看待定，见 [schema-数据契约.md](schema-数据契约.md) 敏感内容策略）。

---

## 1. 五步接入

| 步 | 做什么 | 找谁 / 看哪 |
|---|---|---|
| **① 领 `tool_id`** | 平台管理员给你登记，发一个固定 ID（命名 `<team>-<tool>`） | 平台方调 `POST /registry/tools`，把 ID 给你 |
| **② 读契约** | 了解必填/选填、6 条硬性义务、边角情况 | [contract-接入契约.md](contract-接入契约.md) |
| **③ 按 schema 构造记录** | 拼一条符合统一格式的 JSON | 见下方 §2 最小示例 + [schema-数据契约.md](schema-数据契约.md) |
| **④ 上报** | 在工具里把记录 POST 给接入 API | 见下方 §3 |
| **⑤ 自检 + 验收** | 用 `event.schema.json` 校验格式；按清单验收 | [event.schema.json](../shared/schema/event.schema.json) + [_template/pilot_checklist.md](../integrations/_template/pilot_checklist.md) |

---

## 2. 最小示例（直接抄改）

**契约版本当前 = `v0.2`**（以 [schema-数据契约.md](schema-数据契约.md) 顶部为准）。下面是**非 LLM 工具 / 首轮试点**的最小记录，只含硬性必填（圈一）+ 入口来源：

```json
{
  "record_id": "<你生成的 uuid4，每条唯一>",
  "schema_version": "v0.2",
  "tool_id": "<平台发给你的 ID，如 infra-log-exporter>",
  "conversation_id": "<“一次使用”的聚合键，见下>",
  "start_time": "2026-06-04T08:00:00Z",
  "end_time": "2026-06-04T08:00:02Z",
  "duration_ms": 2000,
  "status": "success",
  "metadata": { "entry_source": "direct", "auth_method": "none" }
}
```

**如果调了大模型**，再补圈二 token 字段（按你家 API 归一化后填）：

```json
  "model": "gpt-4o",
  "prompt_tokens": 120,
  "completion_tokens": 80,
  "total_tokens": 200,
  "cost": 0.0012,
  "cost_source": "source"
```

要点：
- `record_id`：**你自己生成 uuid4**，每条唯一。失败重发用**同一个** `record_id`，平台靠它幂等去重，不会重复入库。
- `conversation_id`：**「一次使用」的聚合键**。一次使用内多次调用模型，用同一个值串起来（如用户点一次「整体导出」触发的若干次调用）。图省事直接塞 `record_id` 也行，但那样"按会话聚合"会退化成"按调用"，使用率维度会失真——尽量给一个真实的会话键。
- `status`：只能是 `success` / `failed` / `timeout`。**失败和超时也必须上报**（这是最有价值的数据）。
- 时间用 ISO-8601 带时区（UTC）。

字段全表（圈一/圈二/圈三逐字段含义、类型、必填）见 **[schema-数据契约.md](schema-数据契约.md)**；机器可校验的唯一真源是 **[event.schema.json](../shared/schema/event.schema.json)**——以它为准自校。

> **要记的东西主表没预置怎么办？**（如「报告类型」「分段耗时」「图片产出」）→ 放进 `metadata`，但**按统一约定的形状记**，见 **[metadata-conventions-metadata约定与字段治理.md](metadata-conventions-metadata约定与字段治理.md)**。没有现成约定就找平台要一条，别自创格式。原文 / 图片二进制有专门规矩（原文走主字段、允许记录、二进制只存引用），也在那份里。

---

## 3. 怎么上报

把上面的 JSON `POST` 到接入 API：

```
POST  http://<平台地址>:8000/events
Content-Type: application/json
（可选）Authorization: Bearer <token>
```

- 成功返回 `202`，body 含 `record_id` / `ingested_at` / `inserted`。
- **校验不过返回 `422`**（圈一缺字段、类型/枚举不对），当场打回、不入库——按返回信息修。

**两种实现方式，二选一：**
1. **抄参考 SDK**（推荐，能改代码的最省事）：[collection/sdk/](../collection/sdk/README.md)，已封装好 token 归一化、入口来源、本地缓冲 + 幂等重试。
2. **自行实现**：任何语言拼 JSON 直接 POST 即可；上线前拿 [event.schema.json](../shared/schema/event.schema.json) 校一遍。

**身份（`user_id` 从哪来）**：
- 工具从平台门户打开（`portal`）或工具自己接了平台 Auth 登录（`direct`）→ 带 `Authorization: Bearer <token>`，平台解析出 `user_id`/`team_id`，**比你 payload 里写的优先**。
- 识别不了身份（`unknown`）→ 不带 token，平台兜底记 `anonymous`，**不阻断入库**。

---

## 4. 你要在工具代码里改什么

在**调用点 / 触发点**加埋点，注意这几条硬性义务（完整版见 [contract-接入契约.md](contract-接入契约.md) §三、§四）：

| 场景 | 怎么改 |
|---|---|
| 普通调用 | 调用**结束后**（拿到结果或失败）拼记录上报 |
| 失败 / 超时 | 一样要上报，`status` 填 `failed`/`timeout`，别只在成功时记 |
| 流式（SSE） | 必须开 usage 返回（OpenAI 兼容接口加 `stream_options.include_usage`），**流结束后**再记完整记录（token 这时才齐） |
| 异步任务（生成图/视频） | 两段式：先提交、后查状态；token 留空，成本用源头返回的 `cost`（`cost_source=source`） |

---

## 5. 待定/边界（接入前请知悉）

- **原文记录已放开**：可上报 `input_content` / `output_content` 原文（写入侧不设门禁）。仅**读取侧**（谁登录后能在看板查看原文）随多用户上线再按角色分级，细则待定，见 [schema-数据契约.md](schema-数据契约.md) 敏感内容策略。
- **黑盒工具兜底（relay）暂未提供**（Phase 2D）：改不了代码的工具暂时接不进来，请排期等待。
- **自助校验 CLI 规划中**：暂以 [event.schema.json](../shared/schema/event.schema.json) 为准自校。

---

## 把什么发给接入方

本指南可单独阅读，但接入方真正实现时还需要**机器源**。发给对方时一并提供（或给仓库 `platform/` 访问权）：

1. 本指南 `platform/docs/integration-guide-接入指南.md`
2. 接入契约 [contract-接入契约.md](contract-接入契约.md)、字段文档 [schema-数据契约.md](schema-数据契约.md)
3. **机器可校验源** [event.schema.json](../shared/schema/event.schema.json)（自校必需）
4. 参考 SDK [collection/sdk/](../collection/sdk/README.md) 与试点模板 [_template/](../integrations/_template/README.md)

并口头交代一件本指南已写明、但易忽略的事：**`tool_id` 找平台领**。（原文可记录，读取侧权限待定。）
