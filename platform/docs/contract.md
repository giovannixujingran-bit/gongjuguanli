# 接入契约 —— 给工具方看的（落地文档）

> 本文档是 Phase 0 产出，承接规划阶段 `规划/数据端/接入契约.md`。
> 字段定义见 [schema.md](schema.md)；机器可校验源是 [`../shared/schema/event.schema.json`](../shared/schema/event.schema.json)；
> `tool_id` 来源见 [工具注册表](../shared/registry/)。
>
> **一句话**：要接入本平台，你只需保证最终落库的那条记录**格式一样**（统一 schema）。怎么采、用什么语言不限。

---

## 一、契约的三样东西

平台不逐个适配工具，而是定一份契约、接入方满足。契约落成三样具体东西：

1. **字段文档** —— [schema.md](schema.md)：每个字段的含义、必填/选填、类型。
2. **机器可校验定义** —— [event.schema.json](../shared/schema/event.schema.json)：数据进入接入层时**自动校验，不合规当场打回**（契约的「牙齿」）。
3. **参考 SDK / 示例** —— Phase 2 产出（`../collection/sdk/`），让能配合的工具直接抄。

---

## 二、字段分级：硬性必填 vs 弹性选填

| 级别 | 字段 | 给不出会怎样 |
|---|---|---|
| **硬性必填（圈一）** | `record_id` / `schema_version` / `tool_id` / `conversation_id` / `start_time` / `end_time` / `duration_ms` / `status` | 入场券，**校验不过当场打回，不许入库** |
| **LLM 专属（圈二）** | `model` / `prompt_tokens` / `completion_tokens` / `total_tokens` / `cost` / `cost_source` | 非 LLM 工具留 NULL，不影响入库 |
| **弹性选填（圈三）** | `user_id` / `team_id` / `result_quality` / `adopted` / `input_content` / `output_content` / `metadata` | 有就多算几个维度；**没有也照收**，绝不因此拒收 |

> `tool_id` **由平台统一分配**：接入前先在[工具注册表](../shared/registry/)登记，平台发固定 ID，你用它对接、每条记录回填。

---

## 三、接入方的硬性义务

- **工具自报为主路**：能改代码的工具，在调用或按钮**触发点**把数据报给平台统一上报 API（参考 SDK 是便捷封装，也可自行实现）。改不了代码的黑盒才走转发服务 / 独立 key 兜底——**转发不是必经总闸**。
- **接住并回传门户注入的身份**：工具从平台入口被打开时，平台注入 `user_id`，上报时原样带回；绕过入口直接使用的记匿名。
- **Token 归一化**：把各家原始 token 字段映射进统一字段（OpenAI `prompt/completion/total`；Claude `input→prompt`、`output→completion`、`total` 自补）。详见 [schema.md](schema.md) 归一化小节。
- **流式调用必须开启 usage 返回**：流式（SSE）默认末尾不带 usage（OpenAI 兼容接口需显式开 `stream_options.include_usage`），不开则 token 全 NULL。token 在流结束时才齐，须在**流结束后**再记完整记录。
- **失败 / 超时也必须上报**：这恰是「哪个工具/中转站不稳定」的关键数据，最易漏记，契约强制。
- **异步任务两段式**：先提交（拿 task id）、后查状态（拿耗时与 `cost`/结果）。采集分两段，token 留 NULL、成本走源头返回的 `cost`（`cost_source = source`）。

---

## 四、必须预先处理的边角情况

| 情况 | 处理 |
|---|---|
| 流式输出 | token 与结果在流结束时才齐，流结束后再记完整记录，不能一发请求就记 |
| 失败 / 超时 | 最易漏记但最关键，契约要求失败也上报 |
| 异步任务类（生成图/视频） | 两段式采集：耗时与结果分两次拿，token 留 NULL，成本走源头 `cost` |
| 「一次使用」界定 | 由工具按触发点自定义（触发式埋点，非平台自动观测）；一次使用内多次调用用同一 `conversation_id` 串联 |
| 不调大模型的工具 | 圈二留 NULL，只记圈一（次数/耗时/status）+（可选）输入输出 / metadata |
| 敏感内容边界 | 见 [schema.md](schema.md) 敏感内容策略一节（待人工确认） |

---

## 五、兜底通道

对既给不全数据、又改不了的工具，让其走**本地转发服务**（Phase 2 产出，`../collection/relay/`），由平台「代它」采集到能采的部分（至少 token + 耗时），按统一格式入库。

> 契约负责「能配合的自己送上门」，兜底负责「不能配合的平台代采、一个不漏」。满足不了完整契约也能进来，只是数据最粗（`data_level = minimal`）。
