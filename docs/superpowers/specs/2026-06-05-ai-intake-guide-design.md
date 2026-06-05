# 设计：AI 接入问诊向导（ai-intake-guide）

> 日期：2026-06-05　状态：待实现
> 目标读者：本仓库维护者（平台方）。本 spec 描述要**新增的一份文档**及其连带改动。

---

## 1. 要解决的问题

现有接入包（`platform/docs/` 的 integration-guide / contract / schema / metadata-conventions + handoff-kit）是**给人读的叙述体**。当接入方用一个 AI 来读这个包做接入时，AI 没有一条结构化的「问诊路径」告诉它：针对**这一个具体工具**该填哪些字段、哪些必须回头问工具方。结果要么瞎猜，要么把一堆开放问题一股脑抛回去，又变成长时间拉扯。

**要做的**：新增一份**给 AI 看的接入剧本**，让接入方的 AI 读它 → 尽量自己从工具代码推断 → 只把真正缺的、属业务判断的挂起来问工具方 → 一次性产出「接入配置 + 接入方案书」。

### 1.1 最高原则：只接数据，绝不影响原工具功能

这是凌驾一切的硬约束，剧本必须把它写在最前面、并在每个埋点判定点重申：

- **上报是旁路，不在主链路上**：埋点放在工具原逻辑**之外/之后**，拿到结果或失败后再上报，绝不挡在用户拿结果的路径上。
- **上报失败必须被吞掉**：上报抛异常 / 平台不可达 / 超时，一律 catch 住、本地 buffer 兜底，**绝不向上抛、绝不阻断工具**。宁可丢这条统计，也不能让用户的操作失败。
- **不改原调用的返回与时序**：不修改工具原本的入参、返回值、错误处理；流式不改流、异步不改任务流程。
- **可一键关停**：保留环境变量开关（如 `PLATFORM_TRACKING_ENABLED=false`，见 `_template/pilot_checklist.md` 回滚节），随时只关上报、不动工具。
- **额外开销可忽略**：上报尽量异步/非阻塞，不引入明显延迟。

剧本里写死一句：**任何拿不准会不会影响原工具的做法，一律选「更不侵入」的那种；影响功能 > 丢统计，永远是这个优先级。**

**明确不做的（YAGNI）**：
- 不做机器可读判定表（YAML/JSON）。剧本用 markdown 决策树即可。
- 不做面向平台方的交互反问。平台侧的事（领 `tool_id`、立新 metadata 约定）只在方案书末尾**列为备注**，不打断 AI 流程。
- 不改任何现有字段 / schema / 契约版本。这是**纯新增文档**，不动数据契约。

---

## 2. 新增文件

`platform/docs/ai-intake-guide.md` —— 「AI 接入问诊向导」。

定位：与 `integration-guide.md` 互补——后者给**人**照着做，前者给**接入方的 AI**照着跑。它不重复字段定义，全部链接到 schema.md / contract.md / metadata-conventions.md（守 SSOT，别处只链不抄）。

### 2.1 剧本结构（三块）

**A. 自助决策树**（每个节点先「从工具代码/上下文推断」，推不出再挂起问）：

| 判定点 | AI 通常能自己定的 | 结论落到哪 |
|---|---|---|
| 能否改代码 | 读代码即知 | 不能改 → 走 relay（Phase 2D 暂未提供），提前止损、不继续 |
| 圈一硬性必填 | `record_id`(uuid4)/`start_time`/`end_time`/`duration_ms`/`status`/`schema_version` 可自动生成或由平台版本决定 | 全工具必填 |
| 调不调大模型、哪家 API | 读调用代码即知 | 调 → 补圈二 `model`/`*_tokens`/`cost`/`cost_source`，并按家做 token 归一化 |
| 流式 / 异步 | 读代码即知 | 流式 → 开 usage、流结束后记；异步 → 两段式、token 留 NULL、`cost_source=source` |
| 产出物（图/文件/文本） | 读产出代码即知 | 按 metadata-conventions 的 `outputs` 约定记，二进制只存引用 |
| 身份 / 入口来源 | 看工具怎么被打开 | 门户注入 `user_id` / 接 Auth(`direct`) / 匿名(`unknown`) |

**B. 反问工具方清单**（只有工具方知道、代码看不出的才挂起）：

- 「一次使用」怎么界定？（决定 `conversation_id` 聚合键——最易失真处）
- 该在哪些触发点埋点？（哪些按钮/调用算一次使用）
- 要不要上报原文 `input_content` / `output_content`？（业务敏感判断）
- 质量信号 `result_quality` / `adopted` 从哪来、要不要记？

规则（剧本里写死）：**能从代码推断的别问；只问业务/产品判断类的；一次性把挂起项列全，不要逐条挤牙膏。**

**C. 两个产出物的模板**（剧本指导 AI 生成，落在 `platform/integrations/<tool_id>/`，沿用 `_template/` 形状）：

1. `tool_config.json` —— 基于 `_template/tool_config.example.json` 填好的**接入配置**。
2. `接入方案.md` —— 人读方案书，固定骨架：工具属哪类 / 上报哪些字段 / 示例事件 JSON / **待工具方确认**清单 / **需平台方处理**备注（领 tool_id 等）。

> **必须写清的一个易混点**：`tool_config.json` 是**接入配置**（这个工具怎么接、用不用 SDK、buffer 路径、`record_raw_content` 开关、`entry_source`/`auth_method` 作为接入设定）。它和**事件 payload** 是两回事——事件里 `entry_source`/`auth_method` 是 `metadata` 字段。剧本要明确区分，避免接入方把配置当事件发。

---

## 3. 连带改动（按 CLAUDE.md §3 改动传播规则）

| 改了什么 | 必须同步 |
|---|---|
| 新增一份规范文档 `ai-intake-guide.md` | 更新 `CLAUDE.md` §1 文档结构表 + `PROJECT_PLAN.md` 文档地图 |
| 要让接入方拿到 | 在 `platform/tools/export_integration_kit.py` 的 `SOURCES` 加一行 `(docs/ai-intake-guide.md, "AI接入向导.md")`；重跑脚本让它进 `handoff-kit/`；同步更新 `说明.txt` 的阅读顺序 |
| 任何改动收尾 | 在 `开发日志.md` 追加一条（倒序） |

**不需要做的**：不升 `schema_version`（不动数据契约）；CHANGELOG 视情况——新增一份给接入方的能力文档可记一条，纯文档可不记，发布时再定。

---

## 4. 验收（怎么算这件事做对了）

- [ ] `platform/docs/ai-intake-guide.md` 存在，内容只链接不复制字段定义（SSOT 不破）。
- [ ] 「只接数据、绝不影响原工具」写在剧本最前，且决策树每个埋点判定点都重申了旁路/吞异常/可关停。
- [ ] 剧本里的决策树覆盖：圈一/圈二/圈三、流式/异步/失败、产出物 outputs、身份/入口、原文记录。每个判定点都标了「先推断、推不出再问」。
- [ ] 反问清单只含「业务判断类」，不含「读代码可知类」。
- [ ] 两个产出物模板与 `_template/tool_config.example.json` 字段一致，且写清了「接入配置 ≠ 事件 metadata」。
- [ ] 重跑 `export_integration_kit.py` 后，`handoff-kit/` 多出「AI接入向导.md」，`说明.txt` 阅读顺序已含它。
- [ ] CLAUDE.md §1、PROJECT_PLAN 文档地图、开发日志均已同步。
- [ ] 所有跨文档链接点开可达（用相对路径、链文件不链中文锚点）。

---

## 5. 不在本次范围

- relay 兜底（Phase 2D）、自助校验 CLI（Phase 2.5）—— 既有规划，本设计不触碰。
- 平台侧的交互（发 tool_id、立 metadata 约定）—— 仍是人对人流程，本设计只在方案书里备注提醒。
