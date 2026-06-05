# AI 接入问诊向导 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一份给接入方 AI 读的「接入问诊向导」文档，并接入现有分发包与维护守则，让 AI 能自助判定字段、只在必要时反问工具方，且绝不影响原工具功能。

**Architecture:** 纯新增一份 markdown（`platform/docs/ai-intake-guide.md`），只链接不复制字段定义（守 SSOT）。通过 `export_integration_kit.py` 进 `handoff-kit/`，并连带更新 `CLAUDE.md` §1、`PROJECT_PLAN.md` 文档地图、`开发日志.md`。不动任何字段/schema/契约版本。

**Tech Stack:** Markdown 文档；Python 3.12（`platform/tools/export_integration_kit.py`，本机用 codex-runtime + .pydeps 跑，见 memory `local-test-env-py-mismatch`）。

设计稿：[docs/superpowers/specs/2026-06-05-ai-intake-guide-design.md](../specs/2026-06-05-ai-intake-guide-design.md)。

---

## File Structure

- **Create** `platform/docs/ai-intake-guide.md` —— 给 AI 看的接入剧本（决策树 + 反问规则 + 两产出物模板）。本计划的主体。
- **Modify** `platform/tools/export_integration_kit.py` —— `SOURCES` 加一行；`render_readme()` 阅读顺序加一条。
- **Regenerate** `platform/integrations/handoff-kit/*` —— 跑脚本生成，**不手改**。
- **Modify** `CLAUDE.md` §1 文档结构 —— docs 列表加一行。
- **Modify** `PROJECT_PLAN.md` 文档地图表 —— 数据端加一行。
- **Modify** `开发日志.md` —— 追加实现条目。

---

### Task 1: 写接入向导正文 `ai-intake-guide.md`

**Files:**
- Create: `platform/docs/ai-intake-guide.md`

- [ ] **Step 1: 写文件，完整内容如下（逐字写入，链接均为 docs/ 内同级文件名，不带中文锚点）**

````markdown
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
````

- [ ] **Step 2: 校验链接目标都存在**

Run（PowerShell，在仓库根）:
```
$f='platform/docs/ai-intake-guide.md'
'integration-guide.md','schema.md','contract.md','metadata-conventions.md' | % { Test-Path "platform/docs/$_" }
'platform/shared/schema/event.schema.json','platform/collection/sdk/README.md','platform/integrations/_template/README.md','platform/integrations/_template/tool_config.example.json','platform/integrations/_template/pilot_checklist.md' | % { Test-Path $_ }
```
Expected: 全部输出 `True`。若有 `False`，修正该链接路径再继续。

- [ ] **Step 3: Commit**

```
git add platform/docs/ai-intake-guide.md
git commit -m "docs(接入): 新增 AI 接入问诊向导 ai-intake-guide.md"
```

---

### Task 2: 接入分发包生成脚本

**Files:**
- Modify: `platform/tools/export_integration_kit.py`

- [ ] **Step 1: 在 `SOURCES` 列表加一行**（在 `metadata-conventions.md` 那行之后、`event.schema.json` 那行之前）

把：
```python
    (ROOT / "docs" / "metadata-conventions.md", "metadata约定.md"),
    (ROOT / "shared" / "schema" / "event.schema.json", "event.schema.json"),
```
改为：
```python
    (ROOT / "docs" / "metadata-conventions.md", "metadata约定.md"),
    (ROOT / "docs" / "ai-intake-guide.md", "AI接入向导.md"),
    (ROOT / "shared" / "schema" / "event.schema.json", "event.schema.json"),
```

- [ ] **Step 2: 在 `render_readme()` 的阅读顺序里加一条**

把：
```python
5. metadata约定.md   —— 要记主表没预置的东西（报告类型/分段耗时/图片产出…）时看这份的统一记法。
```
改为：
```python
5. metadata约定.md   —— 要记主表没预置的东西（报告类型/分段耗时/图片产出…）时看这份的统一记法。
6. AI接入向导.md     —— 用 AI 帮你接入时，把它喂给 AI；它会自助判定字段、只在必要时反问你，并产出接入配置+方案。
```

- [ ] **Step 3: Commit**

```
git add platform/tools/export_integration_kit.py
git commit -m "build(接入): export 脚本纳入 AI接入向导"
```

---

### Task 3: 重生成 handoff-kit 并验证

**Files:**
- Regenerate: `platform/integrations/handoff-kit/*`（脚本产物，勿手改）

- [ ] **Step 1: 跑生成脚本**（本机 Py 环境见 memory `local-test-env-py-mismatch`：codex-runtime Py3.12 + .pydeps）

Run（PowerShell，在 `platform/` 目录下，因脚本用 `from shared...` 相对导入）:
```
cd platform; python tools/export_integration_kit.py; cd ..
```
Expected: 打印 `接入资料分发包已生成：platform/integrations/handoff-kit（契约 vX.Y）`。

> 若本机直接 `python` 跑不通（缺解释器/依赖），用 memory 里记的 codex-runtime 解释器路径跑同一脚本。脚本无第三方依赖，仅需能 import 本仓库 `shared`。

- [ ] **Step 2: 验证产物出现且 README/说明 已含新条目**

Run:
```
Test-Path platform/integrations/handoff-kit/AI接入向导.md
Select-String -Path platform/integrations/handoff-kit/说明.txt -Pattern 'AI接入向导'
```
Expected: 第一行 `True`；第二行匹配到 `6. AI接入向导.md …`。

- [ ] **Step 3: 确认生成文件带「自动生成」横幅（没被手改）**

Run:
```
Get-Content platform/integrations/handoff-kit/AI接入向导.md -TotalCount 1
```
Expected: 输出以 `<!-- 自动生成 by platform/tools/export_integration_kit.py` 开头。

- [ ] **Step 4: Commit**

```
git add platform/integrations/handoff-kit
git commit -m "docs(接入): 重生成 handoff-kit 含 AI接入向导"
```

---

### Task 4: 连带更新守则与文档地图

**Files:**
- Modify: `CLAUDE.md`（§1 文档结构）
- Modify: `PROJECT_PLAN.md`（文档地图表）

- [ ] **Step 1: `CLAUDE.md` §1 docs 列表加一行**

在 `├ docs/integration-guide.md   接入方总入口…` 行之后加：
```
├ docs/ai-intake-guide.md     给接入方 AI 看的接入剧本：决策树自助判定+反问工具方规则+产出配置/方案；最高原则只接数据不影响原工具。【给接入方 AI 看】
```

- [ ] **Step 2: `PROJECT_PLAN.md` 文档地图表加一行**

在「数据端 | [接入指南]…」行之后加：
```
| 数据端 | [AI 接入向导](platform/docs/ai-intake-guide.md) | 给接入方 AI 看的接入剧本：自助判定字段 + 反问工具方规则 + 产出接入配置/方案 | 工具方的 AI | 偶尔 |
```

- [ ] **Step 3: 校验两处链接可达**

Run:
```
Test-Path platform/docs/ai-intake-guide.md
```
Expected: `True`。

- [ ] **Step 4: Commit**

```
git add CLAUDE.md PROJECT_PLAN.md
git commit -m "docs: 文档结构/地图纳入 AI 接入向导"
```

---

### Task 5: 追加开发日志并收尾

**Files:**
- Modify: `开发日志.md`

- [ ] **Step 1: 在最上面（标题与首条之间）追加一条**

在 `---` 分隔符后、`## 2026-06-05 — 接入包新增「AI 接入问诊向导」设计稿…` 之前插入：
```
## 2026-06-05 — 实现 AI 接入问诊向导 + 接入分发包

- **阶段**：Phase 2C 接入工程化（实现）。
- **做了什么**：
  1. 新增 `platform/docs/ai-intake-guide.md`：给接入方 AI 的剧本，决策树自助判定字段、只在业务判断处反问工具方，产出 `tool_config.json` + `接入方案.md`。最高原则「只接数据不影响原工具」写在最前、每步重申。
  2. `export_integration_kit.py` 的 SOURCES + 阅读顺序纳入它，重跑生成 `handoff-kit/AI接入向导.md`。
  3. 连带更新 `CLAUDE.md` §1、`PROJECT_PLAN.md` 文档地图。
- **涉及文件**：新增 `platform/docs/ai-intake-guide.md`；改 `platform/tools/export_integration_kit.py`、`CLAUDE.md`、`PROJECT_PLAN.md`；重生成 `platform/integrations/handoff-kit/*`。
- **关联决策**：无新决策（未改数据契约，不升 schema_version）。

---
```

- [ ] **Step 2: 过 CLAUDE.md §5 自检清单**

逐项确认：SSOT（向导只链接不复制字段定义）✅；无连带漏项（不涉及字段四连动）✅；链接已 Test-Path 验证 ✅；开发日志已追加 ✅；CHANGELOG 纯文档新增、可不写；无新决策；索引（CLAUDE.md §1 + PROJECT_PLAN 地图）已同步 ✅；未改代码逻辑、无机器闸门项。

- [ ] **Step 3: Commit**

```
git add 开发日志.md
git commit -m "docs(日志): 记录 AI 接入向导实现"
```

---

## 完成标准

- `platform/docs/ai-intake-guide.md` 存在，只链接不复制字段定义。
- 跑 `export_integration_kit.py` 后 `handoff-kit/AI接入向导.md` 出现、带自动生成横幅、`说明.txt` 阅读顺序含它。
- `CLAUDE.md` §1、`PROJECT_PLAN.md` 文档地图、`开发日志.md` 均已同步。
- 全程未改任何字段/schema/契约版本。
