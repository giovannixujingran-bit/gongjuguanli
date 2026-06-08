# CLAUDE.md —— 本项目文档维护守则

> 这份文件规范「**怎么维护这套规划/规范文档**」，不是业务内容本身。
> 任何人（含 AI）在本目录动 `.md` 之前，先读这份。Claude Code 每次开新会话会自动预读它。
> 业务内容的总入口是 [PROJECT_PLAN.md](PROJECT_PLAN.md)。
>
> **本文件的定位**：它就是「每次操作前先预读的规则文档」。要团队/多端共享，必须纳入 Git 一起版本管理，不要散落在单机；它本身的修改也走版本记录。

---

## 0. 项目一句话

公司局域网内的统一平台，汇总各类工具的每一次使用，做成本 / ROI / 使用率 / 质量四类分析。由**两个前端（使用端·使用者门户 / 数据端·后台分析台）+ 共享后端**组成。当前阶段：**Phase 2A/2B 最小实现已完成；下一步执行真实数据库冒烟与 Phase 2C 真实工具试点验证。**

---

## 远程仓库与版本发布

- **远程仓库（GitHub）**：<https://github.com/giovannixujingran-bit/gongjuguanli> —— 本仓库的唯一远程。源码 + 全部规范文档都在这里，新人/AI 可从此处克隆并读 `CLAUDE.md` 入门。
- **版本号规范（SemVer）**：`主.次.补丁`，tag 形如 `v0.0.1`。早期（主版本 0）接口仍可不兼容变动；`次` 升＝新增能力，`补丁` 升＝修复/小改。**事件数据契约另有独立的 `schema_version`**（见 [schema-数据契约.md](platform/docs/schema-数据契约.md)），与本仓库版本号**不是一回事**，别混。
- **每个 tag 对应 [CHANGELOG.md](CHANGELOG.md) 的一个发布块**：发布时把 `## Unreleased` 改名为 `## vX.Y.Z — 日期`，顶部再留一个空的 `## Unreleased` 供后续累积。
- **发版步骤**：① 整理 `CHANGELOG.md`（Unreleased → 版本号 + 日期）；② 提交；③ 打带注释 tag：`git tag -a vX.Y.Z -m "..."`；④ `git push && git push --tags`。机器闸门须全绿才发（见 §5 / [code-standards-代码规范.md](platform/docs/code-standards-代码规范.md)）。
- **当前最新发布**：`v0.1.0`（AI 接入向导 + `platform/docs/` 文档改名「英文-中文」+ 采集表述订正；前作 `v0.0.1` 含 Phase 0–2B 闭环 + 迁移执行器）。

---

## 1. 文档结构（单一信息源）

```
PROJECT_PLAN.md              总纲/索引：定位 + 文档地图 + 决策记录。不放具体规范内容。
开发日志.md                  按时间的过程流水（倒序）。每次改动追加一条。
CHANGELOG.md                 面向阶段/发布的变更摘要。只记能力变化，不记过程流水。
platform/                    代码区 + 全部规范文档（唯一 SSOT，原 规划/ 已退役并入此处）：
├ docs/architecture-架构与原则.md        项目是什么、三原则、五层架构、两个前端+共享后端、三类工具、入口门户与账号体系。【稳定】
├ docs/execution-plan-执行计划与技术栈.md      分阶段计划、技术栈、platform/ 目录结构、交接命令。【每阶段更新】
├ docs/code-standards-代码规范.md      工程纪律：单向依赖、schema 代码生成、删不注释、CI 机器闸门。【写代码前必读】
├ docs/schema-数据契约.md              统一事件 Schema（三圈字段），带契约版本号；机器源 shared/schema/event.schema.json。【随 schema_version 演进】
├ docs/registry-工具注册表.md            tool_id 来源 + 门户展示字段，两端共读。【偶尔】
├ docs/metadata-conventions-metadata约定与字段治理.md metadata 怎么记（统一形状）+ 字段三层模型 + 晋升流程。【接入方记新字段前看】

├ docs/integration-guide-接入指南.md   接入方总入口：五步流程+最小示例+边界，可直接发给接入方。【给工具方看·先读】
├ docs/ai-intake-guide-AI接入向导.md     给接入方 AI 看的接入剧本：决策树自助判定字段+反问工具方规则+产出配置/方案；最高原则只接数据不影响原工具。【给接入方 AI 看】
├ docs/contract-接入契约.md            接入义务、边角情况、兜底。【给工具方看·细则】
├ docs/portal-工具门户.md              分类卡片、排序逻辑、AI 工具推荐。【使用端前端规划】
└ backend / collection / shared / integrations / apps  代码：接入 API、生成模型、存储层、参考 SDK、demo、Auth API、试点模板；relay/分析层/前端仍占位。
   （integrations/handoff-kit/＝接入资料分发包，由 tools/export_integration_kit.py 从接入文档生成，非 SSOT，勿手改。）
```

**单一信息源（SSOT）铁律**：每个事实只在一个文件里定义，别处只**链接**、不复制。
- 字段定义只在 `platform/docs/schema-数据契约.md`（机器源 `platform/shared/schema/event.schema.json`）。
- 工具注册表（含展示字段）只在 `platform/docs/registry-工具注册表.md`。
- metadata 语义约定 + 字段三层治理 / 晋升流程只在 `platform/docs/metadata-conventions-metadata约定与字段治理.md`。
- 架构图只在 `platform/docs/architecture-架构与原则.md`。
- 阶段/部署命令、目录结构只在 `platform/docs/execution-plan-执行计划与技术栈.md`。
- 使用端门户规划只在 `platform/docs/portal-工具门户.md`。
- 决策结论只在 `PROJECT_PLAN.md` 的「决策记录」。
- 过程流水只在 `开发日志.md`；阶段 / 发布摘要只在 `CHANGELOG.md`。

发现同一内容在两处都写了 → 是 bug，删一处、改成链接。

### SSOT 位置（已统一，不再有双轨）

历史上规范曾住在 `规划/`，并随 Phase 0 起逐份向 `platform/` 转移。**截至 [决策 #30](PROJECT_PLAN.md)，迁移已全部完成**：`规划/` 目录已退役删除，**所有规范文档现在只有一个 SSOT 位置 `platform/docs/`**：

- 数据契约 → [platform/docs/schema-数据契约.md](platform/docs/schema-数据契约.md) + [event.schema.json](platform/shared/schema/event.schema.json)（机器源）+ `platform/backend/storage/migrations` 建表 SQL（三者一致）。
- 接入契约 → [platform/docs/contract-接入契约.md](platform/docs/contract-接入契约.md)。
- 架构 / 执行计划 / 代码规范 / 工具注册表 / 工具门户 → `platform/docs/` 下的 `architecture-架构与原则.md` / `execution-plan-执行计划与技术栈.md` / `code-standards-代码规范.md` / `registry-工具注册表.md` / `portal-工具门户.md`。

改任何规范，直接改 `platform/docs/` 对应文件（数据契约还要连带机器源 + 建表 SQL，见 §3）。不再有「改 platform 还是改规划」的判断。

---

## 2. 按任务读哪份（开工前必读）

| 你要做的事 | 先读 | 可能要改 |
|---|---|---|
| 改字段 / schema | **platform/docs/schema-数据契约.md** + platform/shared/schema/event.schema.json | platform/docs/schema-数据契约.md + event.schema.json + 建表 SQL +（连带见 §3） |
| 改工具注册表（接入字段 / 展示字段） | platform/docs/registry-工具注册表.md | registry-工具注册表.md +（连带见 §3） |
| 改接入规则 / 边角情况 / 兜底 | **platform/docs/contract-接入契约.md** | platform/docs/contract-接入契约.md |
| 改使用端门户（卡片 / 排序 / AI 推荐） | platform/docs/portal-工具门户.md | portal-工具门户.md |
| 改架构 / 原则 / 工具分类 / 两端关系 | platform/docs/architecture-架构与原则.md | architecture-架构与原则.md |
| 改阶段计划 / 技术栈 / 目录结构 / 交接命令 | platform/docs/execution-plan-执行计划与技术栈.md | execution-plan-执行计划与技术栈.md |
| 记录一个新的决策/取舍 | PROJECT_PLAN.md | PROJECT_PLAN「决策记录」 |
| 记录阶段/发布摘要 | CHANGELOG.md | CHANGELOG |
| **写/改任何代码** | platform/docs/code-standards-代码规范.md | 代码 +（机器闸门必须全绿） |
| 不确定改哪 | PROJECT_PLAN.md 文档地图 | —— |

任何编辑前**先 Read 目标文件全文**，理解上下文再改，禁止盲改。

---

## 3. 改动传播规则（改了 A 必须同步 B）

文档之间有依赖，改一处常常牵连别处。改完**逐条核对**：

> **铁律：任何改动（文档或代码）完成后，必须在 [开发日志](开发日志.md) 追加一条**（倒序，最新在上）。涉及决策的引用决策记录编号，不复述理由。
> **CHANGELOG 规则**：不是每次小改都写。只有阶段完成、可运行能力变化、对使用/部署/接入有影响的变更、破坏性变更、迁移事项，才更新 [CHANGELOG.md](CHANGELOG.md)。

| 改了什么 | 必须同步更新 |
|---|---|
| **数据契约（🧊 已冻结，改 platform/docs/schema-数据契约.md）的任何字段**（增删改字段、改类型/枚举/必填） | ① 升 `platform/docs/schema-数据契约.md` 顶部的**契约版本号**；② 在 `PROJECT_PLAN` 决策记录追加一条「为什么改」；③ 连带改 `platform/shared/schema/event.schema.json` 与 `platform/backend/storage/migrations` 建表 SQL（**三者一致**）；④ 重跑 `platform/scripts/gen-models` 重生成模型 |
| **工具注册表字段（platform/docs/registry-工具注册表.md）**（接入字段或门户展示字段） | 检查 `docs/schema-数据契约.md` 里 `tool_id` 引用、`docs/portal-工具门户.md` 对展示字段的引用、`docs/execution-plan-执行计划与技术栈.md` 建表 SQL 说明；**不升事件契约版本**（注册表不属事件 schema） |
| **新增/改一条 metadata 语义约定（platform/docs/metadata-conventions-metadata约定与字段治理.md）** | 只改该文档第三节（约定库）+ 标生效日期；**不升事件契约版本**（metadata 是 event.schema.json 里的自由对象，约定是 prose 规范，不阻断入库）。若要重新分发，重跑 `export_integration_kit.py`。**注**：把某个 metadata 字段「晋升」为主表列，属数据契约变更，走上一行的四连动 |
| **改了接入方要看的文档**（`docs/integration-guide-接入指南.md` / `docs/contract-接入契约.md` / `docs/schema-数据契约.md` / `shared/schema/event.schema.json`） | 若要重新分发给外部接入方，重跑 `python platform/tools/export_integration_kit.py` 重新生成 `platform/integrations/handoff-kit/`（接入资料分发包）。**勿手改 handoff-kit/ 内文件**——它是上述文档的生成副本、非 SSOT（同 `shared/contracts/` 的生成物对待） |
| **新增/改名一份规范文档** | 更新 `PROJECT_PLAN` 的「文档地图」表 + `CLAUDE.md` §1 结构 |
| **完成一个 Phase / 发布一个可用能力 / 改变部署或接入方式** | 更新 `CHANGELOG.md`；若形成新取舍，同步 `PROJECT_PLAN` 决策记录；再按铁律追加 `开发日志.md` |
| **改架构层次/原则/两端关系** | 检查 数据契约 / 工具注册表 / 接入契约 / 工具门户 / 执行计划 / 代码规范 里引用该架构的地方是否还成立 |
| **改使用端门户（platform/docs/portal-工具门户.md）** | 若涉及注册表展示字段或排序取数，检查 `docs/registry-工具注册表.md`、`docs/schema-数据契约.md` 是否需同步 |
| **定了一个之前「待定」的事项**（如敏感策略、ROI 信号、价格表、门户排序窗口、AI 推荐模型） | 改对应正文 + 把 `PROJECT_PLAN` 决策记录里那条从「待定」改为结论 |
| **任何跨文档链接涉及的标题改名/移动文件** | 修正所有指向它的相对链接（`platform/docs/` 内同级互链直接用文件名；中文锚点不可靠，宁可链接到文件不带 `#` 片段） |

---

## 4. 长期维护原则

1. **重构，不打补丁。** 需求变了就把相关段落改对、改顺，不要在末尾贴「补充说明 / 更正 / 注意其实是……」。文档要永远读起来像一次写成的。发现旧结论错了，直接改正文 + 在决策记录里留一句「原 X 改为 Y，因为 Z」。
2. **决策入账，不是入正文。** 「为什么这么定」的取舍记到 `PROJECT_PLAN` 决策记录（追加，按序）；正文只写「现在是怎样」，不堆历史争论。决策记录追加久了会变长，可定期把已被推翻的条目标「已废弃」或合并，别无限堆叠成另一种补丁。
3. **契约带版本，向后可追。** `platform/docs/schema-数据契约.md` 每次实质改动升版本号；记录里的 `schema_version` 就是据此盖章。
4. **稳定与易变分离。** 别把易变内容（字段、价格、阶段）塞进稳定文档（架构/原则），反之亦然。这是当初拆分的初衷，维护时别又混回去。
5. **占位明确。** 未定的事项统一写「**待定，需人工确认**」并说清待定的是什么，不要含糊带过、也不要擅自替用户拍板（尤其敏感内容策略、ROI 价值信号）。
6. **最小改动。** 一次只解决一件事；不顺手做无关重排，方便 review 和回溯。
7. **守则自身也要维护。** 新增一类文档、SSOT 转移、拆分结构变化时，同步更新这份 `CLAUDE.md`（§1 结构、§2/§3 表）。守则过时比没有守则更危险。
8. **日志与变更摘要分工。** `开发日志.md` 是过程账本：每次改动都写，方便追溯“今天动了哪些文件”。`CHANGELOG.md` 是能力摘要：只写阶段 / 发布级变化，方便快速理解“现在项目能做什么”。两者不要互相复制整段内容。

---

## 5. 改完自检清单（每次编辑收尾必过）

声称「改好了 / 都同步了」之前，逐项核对：

- [ ] **SSOT**：改的内容没在别处复制；别处只是链接。规范的 SSOT 一律在 `platform/docs/`（`规划/` 已退役）。
- [ ] **连带项（§3）**：该表里涉及的同步项全做了（尤其改字段的「升版本号 + 决策记录 + event.schema.json + 建表 SQL」四连动）。
- [ ] **链接有效**：新增/改动的跨文档链接**实际点开验证过**能跳到目标；改过标题就检查所有指向它的链接。不靠中文 `#` 锚点。
- [ ] **开发日志**：已在 [开发日志](开发日志.md) 追加一条（任何改动都要，这是必做项）。
- [ ] **CHANGELOG**：若本次完成阶段、发布能力、改变部署/接入方式、产生破坏性变更或迁移事项，已更新 [CHANGELOG.md](CHANGELOG.md)；纯小修不用写。
- [ ] **决策记录**：有新取舍/更正的，已在 `PROJECT_PLAN` 追加一条。
- [ ] **占位**：未定事项写了「待定，需人工确认」，没有擅自替用户拍板。
- [ ] **索引同步**：动了文档结构的，`PROJECT_PLAN` 文档地图 + 本文件 §1 已更新。
- [ ] **改了代码**：[代码规范](platform/docs/code-standards-代码规范.md) 的机器闸门全绿（格式化/lint/类型/死代码/分层/测试）；废弃代码已删除而非注释保留；无 `_old`/`_v2` 残留文件。

没逐项过完，不算改完，不要声称完成。

---

## 6. 写法约定

- 语言：简体中文为主，字段名/技术名保留英文。
- 文档间一律用**相对链接**互跳；跨文档引用优先链接到文件，少用脆弱的中文 `#` 锚点。
- 表格优先于长段落，规范类内容尤其如此。
- 不引入与当前讨论无关的新设计；有新想法先进 `PROJECT_PLAN` 决策记录讨论，定了再落正文。
