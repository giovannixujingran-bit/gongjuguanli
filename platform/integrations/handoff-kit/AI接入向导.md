<!-- 自动生成 by platform/tools/export_integration_kit.py —— 勿手改。源文件：platform/docs/ai-intake-guide.md。改源后重跑脚本重生成本包。 -->

# AI 接入问诊向导 —— 给接入方的 AI 看的剧本

> **这份给谁**：接入方用一个 AI（如 Claude Code）来帮自己的工具接入本平台时，把这份连同接入包一起喂给它。它是**剧本**，不是给人读的叙述——人读 [integration-guide.md](integration-guide.md)，AI 读这份。
>
> **怎么用**：AI 顺着下面的「决策树」走，**能从工具代码/上下文推断的就直接填，推不出或属业务判断的才挂起来问工具方**，最后产出两样东西（§4）。字段定义一律链到 [schema.md](schema.md) / [contract.md](contract.md) / [metadata-conventions.md](metadata-conventions.md)，本文不复制。

---

## 0. 最高原则（凌驾一切，每步都要守）

**只接数据，绝不影响原工具功能。** 拿不准会不会影响原工具时，一律选更不侵入的做法——**影响功能 > 丢统计，永远是这个优先级。**

- **旁路埋点**：上报放在工具原逻辑**之外/之后**，拿到结果或失败后再上报，绝不挡在用户拿结果的路径上。
- **上报失败一律吞掉**：上报抛异常 / 平台不可达 / 超时，全部 catch 住、走本地 buffer 兜底，**绝不向上抛、绝不阻断工具**。宁可丢这条统计，也不让用户操作失败。
- **不改原返回与时序**：不动工具原本的入参、返回值、错误处理；流式不改流，异步不改任务流程。
- **可一键关停**：留环境变量开关（如 `PLATFORM_TRACKING_ENABLED=false`），随时只关上报、不动工具。
- **开销可忽略**：上报尽量异步/非阻塞，不引入明显延迟。

> 参考 SDK（[collection/sdk/](../collection/sdk/README.md)）已封装本地 buffer + 幂等重试，用它最省心；自行实现也必须满足上面五条。

---

## 1. 决策树（顺着走，能填则填，推不出再问）

每个判定点先尝试**读工具代码/上下文**自己定；定不了的，记进 §3 反问清单。

| 判定点 | 怎么自己定 | 结论 |
|---|---|---|
| **能否改代码** | 看工具是否有可改的调用/触发点 | 不能改 → 走 relay 兜底（**Phase 2D 暂未提供**，见 [contract.md](contract.md)），先止损、不继续接 |
| **圈一硬性必填** | 全部可由埋点自动产生 | `record_id`=uuid4（每条唯一，失败重发用同一个）；`schema_version`=平台当前版本（见 [schema.md](schema.md) 顶部）；`tool_id`=平台发的；`start_time`/`end_time`/`duration_ms`/`status` 埋点时测。全工具必填，缺则被 422 打回 |
| **调不调大模型、哪家 API** | 读调用代码 | 调 → 补圈二 `model`/`prompt_tokens`/`completion_tokens`/`total_tokens`/`cost`/`cost_source`，并按家做 **token 归一化**（OpenAI 原样；Claude `input→prompt`/`output→completion`/total 自补，见 [schema.md](schema.md)）。不调 → 圈二留 NULL |
| **是否流式（SSE）** | 读调用代码 | 是 → 必须开 usage（OpenAI 兼容接口加 `stream_options.include_usage`），**流结束后**才记完整记录（token 这时才齐） |
| **是否异步任务（生成图/视频）** | 读任务提交/查询代码 | 是 → 两段式采集（先提交后查状态），token 留 NULL，成本走源头返回 `cost`、`cost_source=source` |
| **产出物（图/文件/文本）** | 读产出代码 | 按 [metadata-conventions.md](metadata-conventions.md) 的 `outputs` 约定记；**二进制绝不入库**，只存引用 + 尺寸/数量/格式；文本原文走主字段 `output_content`、指标走 `output_chars` |
| **身份 / 入口来源** | 看工具怎么被打开 | 从门户打开 → 带 `Authorization: Bearer <token>`，`metadata.entry_source=portal`；自己接了平台 Auth → `direct`；识别不了 → 不带 token、`unknown`，平台兜底记 `anonymous`、不阻断入库 |
| **失败/超时埋点** | 在错误处理处 | 失败也必须上报，`status` 填 `failed`/`timeout`（最有价值的数据，最易漏）。注意仍守 §0：上报本身失败要吞掉 |

> 整体耗时用圈一现成的 `duration_ms`，别在 metadata 里重造。

---

## 2. 哪些能自己定、哪些必须问

- **能从代码看出来的，别问、直接做**：调不调模型、哪家 API、流式与否、异步与否、产出什么类型、失败处理在哪。
- **只有工具方/产品才知道的，才问**（见 §3）。
- 一次性把要问的列全，**不要逐条挤牙膏**。

---

## 3. 反问工具方清单（只问业务判断类）

把下面这些拿不准的，整理成一张清单一次性问工具负责人，附上你的建议默认值：

- **「一次使用」怎么界定？** 决定 `conversation_id` 这个聚合键。一次使用内多次调模型要用同一个值串起来；图省事直接塞 `record_id` 会让「按会话聚合」退化成「按调用」，使用率维度失真。问清楚业务上一次「使用」是什么。
- **该在哪些触发点埋点？** 哪些按钮/调用算一次使用（触发式埋点，平台不自动观测）。
- **要不要上报原文 `input_content` / `output_content`？** 原文写入侧已放开、可记录（读取侧权限待定，见 [schema.md](schema.md) 敏感内容策略），但记不记是工具方的业务敏感判断。
- **质量信号 `result_quality` / `adopted` 从哪来、要不要记？** 有就多算几个维度，没有也照收。

> 平台侧的事（领 `tool_id`、某个新 metadata 要不要立约定）**不在反问范围**——它要找平台方，不是工具方。把它放进 §4 方案书末尾的「需平台方处理」备注即可，别打断流程。

---

## 4. 产出两样东西

跑完决策树、问完工具方，在 `platform/integrations/<tool_id>/`（沿用 [_template/](../integrations/_template/README.md) 形状）产出：

### 4.1 `tool_config.json` —— 接入配置

基于 [_template/tool_config.example.json](../integrations/_template/tool_config.example.json) 填好。字段含义见该模板与 [_template/pilot_checklist.md](../integrations/_template/pilot_checklist.md)。

> **关键区分，别搞混**：`tool_config.json` 是**接入配置**（这个工具怎么接：用不用 SDK、`events_endpoint`、`buffer_path`、`record_raw_content` 开关、`entry_source`/`auth_method` 作为接入设定）。它**不是**要上报的事件 payload——事件里 `entry_source`/`auth_method` 是 `metadata` 字段。配置回答「怎么接」，事件回答「上报什么」。

### 4.2 `接入方案.md` —— 人读方案书

固定骨架：

1. **工具属哪类**：调不调模型 / 流式 / 异步 / 产出什么。
2. **要上报哪些字段**：圈一（全填）+ 圈二（调模型才填）+ 圈三（按需）+ metadata（entry_source/auth_method/产出物…）。
3. **示例事件 JSON**：照本工具实际拼一条最小记录（参照 [integration-guide.md](integration-guide.md) §2）。
4. **待工具方确认清单**：§3 那几条没定的，列出来 + 建议默认值。
5. **需平台方处理**（备注，不打断）：领 `tool_id`、若有新 metadata 要不要立约定。

---

## 5. 自检（产出前过一遍）

- [ ] 圈一八个字段都安排了来源；流式/异步/失败的特殊处理都考虑了。
- [ ] 每个埋点都守 §0：旁路、上报失败吞掉、不改原返回、可关停。
- [ ] 上线前拿 [event.schema.json](../shared/schema/event.schema.json) 把示例事件自校一遍（圈一缺字段/类型错会被 422 打回）。
- [ ] 反问清单只含业务判断类，平台侧事项进了「需平台方处理」备注。
