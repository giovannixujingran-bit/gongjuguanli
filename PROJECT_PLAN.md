# 内部工具汇总与分析平台 —— 总纲

> 本文件是入口/索引。规范内容全部在 `platform/docs/`（schema / contract / architecture / execution-plan / code-standards / registry / portal）。
> 一句话：把公司各类工具（自写 / 开源自部署 / 黑盒）的**每一次使用**汇总记录，在统一数据契约之上做成本、ROI、使用率、质量四类分析。平台由**两个前端（使用端·使用者门户 / 数据端·后台分析台）+ 共享后端**组成。
> **当前阶段：Phase 2A/2B 最小实现已完成；下一步执行真实数据库冒烟与 Phase 2C 真实工具试点验证。**

---

## 文档地图

规范文档现已全部统一在 `platform/docs/`（原按「端」分组的 `规划/` 目录已退役，见决策 #30）。下表「面向」一列保留原四分（总则 / 共享层 / 数据端 / 使用端）仅作阅读分类。

| 面向 | 文档 | 内容 | 主要读者 | 变更频率 |
|---|---|---|---|---|
| 总则 | [架构与原则](platform/docs/architecture.md) | 项目是什么、三条核心原则、五层架构、两个前端+共享后端、三类工具、入口门户与账号体系 | 决策者 / 新人 | 几乎不变 |
| 总则 | [执行计划](platform/docs/execution-plan.md) | 分阶段计划、技术栈、`platform/` 目录结构、给 AI 的部署命令 | 建平台的团队 | 每完成一阶段 |
| 总则 | [代码规范](platform/docs/code-standards.md) | 工程纪律：单向依赖、schema 代码生成、删不注释、CI 机器闸门 | 写代码的人/AI | 偶尔 |
| 共享层 | [数据契约](platform/docs/schema.md) | 统一事件 Schema（三圈字段），**带契约版本号** | 开发 + 接入方 | 跟 schema_version 演进 |
| 共享层 | [工具注册表](platform/docs/registry.md) | `tool_id` 来源 + 门户展示字段，两端共读 | 开发 / 接入方 / 门户 | 偶尔 |
| 共享层 | [metadata 约定与字段治理](platform/docs/metadata-conventions.md) | metadata 怎么记（统一形状）+ 字段三层模型 + 晋升流程 | 开发 + 接入方 | 跟约定演进 |
| 数据端 | [接入指南](platform/docs/integration-guide.md) | 接入方总入口：五步流程 + 最小示例 + 边界，可直接发给接入方 | 工具方（接入方） | 偶尔 |
| 数据端 | [接入契约](platform/docs/contract.md) | 接入义务、边角情况、兜底通道 | 工具方（接入方） | 偶尔 |
| 使用端 | [工具门户](platform/docs/portal.md) | 分类卡片、排序逻辑、AI 工具推荐 | 建使用端的团队 | 跟门户演进 |
| —— | [开发日志](开发日志.md) | 按时间的过程流水（做了什么、动了哪些文件） | 全员 | 每次改动 |
| —— | [CHANGELOG](CHANGELOG.md) | 面向阶段 / 发布的能力变更摘要 | 全员 / 交接者 | 阶段完成或发布时 |

> 机器可校验源：[event.schema.json](platform/shared/schema/event.schema.json)（数据契约唯一源，后端/前端模型均由它生成）。
> 代码区结构（`platform/`：两个前端 + 共享后端 + 集成层）见 [执行计划](platform/docs/execution-plan.md) 第二节。

---

## 决策记录（这几轮讨论谈定的取舍）

按时间顺序记录「为什么这么定」，避免日后重复争论。

1. **schema 独立版本化**：每条记录带 `schema_version`，区别于代码/Git 版本。
2. **记录粒度 = 一次 API 调用 + `conversation_id` 聚合**：成本要按调用精确，使用率/ROI 按会话聚合，两个粒度都不丢。
3. **token 归一化在采集端**：各家字段名不同（OpenAI prompt/completion vs Claude input/output），平台只定统一目标字段，映射由采集端按契约完成。
4. **缓存/推理 token 不设列**：对接的 APIMart 不返回此类拆分，需要时进 metadata，不动主表。
5. **`cost` + `cost_source`**：成本可空，且区分「源头直接返回（如异步任务）」与「分析层按价表算」。
6. **价格→金额换算后置**：先保证 token 计数准，金额换算待将来用带生效时间的价格表再做。
7. **不做写入侧鉴权**：内部局域网、tool_id 由平台统一分配，伪造不在威胁模型内；真正要管的是读取侧（谁能看原文），并入敏感策略。
8. **留存策略后置**：随公司服务器部署再定。
9. **tool_id 由平台统一分配** → 需要工具注册表（接入管理底表）。
10. **SDK 异步上报带本地缓冲 + 重试队列**：靠 record_id 幂等去重，避免「最该记时丢数据」。
11. **契约硬性义务**：流式必须开 usage、失败/超时必须上报、异步两段式。
12. **ROI 的产出/价值待定**：分子靠人工打分/采纳/业务回填，信号未定，先用 result_quality、adopted 占位。
13. **技术栈锁定 Python**：后端（接入/分析/SDK）用 Python + FastAPI + Pydantic，前端看板 React/TS，relay 默认 Python、必要时单独用 Node。因项目重心在数据分析与 LLM 埋点，正是 Python 主场；relay 是隔离可替换组件，单拆不影响主干。
14. **靠机器闸门治代码混乱**：针对「越写越乱/残留/AI 不敢删」，不只靠规范文档，而是 CI + pre-commit 强制格式化/lint/类型/**死代码扫描**/分层依赖/测试，任一不过不许合并。详见 [代码规范](platform/docs/code-standards.md)。
15. **设开发日志，改动必记**：新增 [开发日志](开发日志.md)，按时间倒序记过程流水；CLAUDE.md 立规——任何文档或代码改动完成后都要追加一条。与决策记录分工：日志记「做了什么」，决策记录记「为什么」。
16. **平台升级为统一入口门户**：不止被动汇总，使用者从平台登录、由入口打开工具，平台据此把「是谁在用」注入使用记录。原「被动汇总站」定位改为「汇总 + 入口门户」。
17. **新增用户账号体系**：一人一号、管理员发放初始账号密码、用户自改、库内存哈希不存明文（内网威胁模型，呼应 #7）。它是 `user_id` 的来源，也是读取侧权限（按人分级）的挂靠点；与工具注册表（管工具，#9）分工。读取侧权限细则仍待定，需人工确认。
18. **`user_id`/`team_id` 改为「门户注入，否则匿名」**：走入口的注入真人，绕过入口 / 黑盒记匿名；**始终不阻断入库**（匿名是兜底值，绝不因拿不到人而拒收，沿用「不把选填设成会拒收的必填」）。触发契约升 v0.2。
19. **采集主路 = 工具自报**：能改代码的工具在调用/触发点直接上报，参考 SDK 仅为其便捷封装；转发服务 / 独立 key 仅作黑盒兜底、非必经总闸（与 #13 relay 隔离定位一致）。
20. **`input_content`/`output_content` 改为通用选填**：不再限大模型，任何工具（含非 LLM）皆可记，受敏感策略约束。触发契约升 v0.2。
21. **「一次使用」由工具按触发点自定义**：触发式埋点而非平台自动观测（如点击「整体导出」即一次）；一次使用内多次调用用同一 `conversation_id` 聚合（细化 #2 的会话聚合）。
22. **平台拆为「两个前端 + 共享后端」，文档与代码按使用端 / 数据端 / 共享层三分**：原单一平台叙事明确为**使用端·使用者门户**（工具启动器，原属隐性）与**数据端·后台分析台**（原看板）两个并列前端，共用同一套采集/存储/分析/账号/注册表。规划文档随之重组为 `规划/`（总则 / 共享层 / 数据端 / 使用端 四组），代码区 `platform/` 按「两个前端 + 共享后端 + 集成层」组织。门户因此成为一等前端（落实 #16 的入口门户定位）。
23. **工具注册表升级为共享资产，增门户展示字段**：原仅服务数据端的注册表（#9）增加 `category`/`display_name`/`description`/`icon`/`thumbnail`/`launch_url`/`sort_weight`/`enabled`，成为使用端门户工具目录的底表，`tool_id` 仍为两端共用主键。其中 `thumbnail`（功能缩略图）用于卡片主体（见 #25）。注册表不属事件 `schema_version` 范畴，改它不升事件契约版本。
24. **新增使用端三大功能与一处后置 AI**：① 分类卡片工具列表（读注册表 `category`）；② 排序逻辑（用户自定义偏好 > 使用频次/时间自动排 > `sort_weight` 兜底，使用数据取自共享层事件表只读聚合）；③ AI 工具推荐（按用户需求语义匹配注册表 `description`）。后台看板的「AI 数据分析」助手**待定、后置**，仅留位。排序取数窗口、偏好存储位置、AI 推荐是否计入统计、用哪家模型均**待定，需人工确认**。

25. **使用端门户 UI 定稿**：布局取「**居中搜索框 + 向下分区**」（启动器风，桌面优先）；**浅 / 深双主题**，同一套布局只换配色、顶栏（吸顶）放日 / 夜切换、默认浅色。首屏先「**我的收藏** + 最近使用」再分类分区。卡片为**图片式媒体卡**——`thumbnail` 功能缩略图占主体（缺图自动生成「icon+名称+色块」占位图）+ icon + display_name + 一句 description + 收藏星标。搜索框打字即时本地过滤（零 token），AI 推荐由显式「✨ 推荐工具」按钮触发（按需调用、省 token）；收藏 ☆ 入「我的收藏」、区内可拖拽排序。门户必须登录才进。该 UI 已**纳入正式方案**，以可点视觉参考稿 [门户首页-mockup.html](platform/docs/mockups/门户首页-mockup.html) 为视觉基准（已确认；规范 SSOT 仍是 §三，参考稿不另立 SSOT）。详见 [使用端/工具门户](platform/docs/portal.md) §三。

26. **产出 Phase 0 实质内容，并先 git init 建基线；`规划/` 冻结方式待人工确认**：执行交接命令的「严格 Phase 0」，在 `platform/` 落地数据契约 v0.2 的 JSON Schema（[event.schema.json](platform/shared/schema/event.schema.json)，唯一源）、落地文档（[schema.md](platform/docs/schema.md)/[contract.md](platform/docs/contract.md)）、三表建表 SQL（事件表/工具注册表/用户账号表）、`README`/`docker-compose` 骨架、机器闸门配置（ruff/mypy/vulture/import-linter/pytest + 前端 eslint/prettier/tsc/knip + pre-commit/CI + schema→模型代码生成），强度放原型档。不实现任何业务逻辑、不接真实工具、零硬编码密钥、敏感策略留占位。**原非 Git 仓库**，按 CLAUDE.md「规范须纳入版本管理」先 `git init` 提交基线。**关于冻结**：CLAUDE.md 规定建表 SQL 生成即触发 `规划/` 冻结 + SSOT 转移到 `platform/docs/`；但本轮只产出了 schema / 接入契约的 platform 对应物，**架构与原则 / 执行计划 / 代码规范 / 工具注册表 / 工具门户尚无 platform/ 等价文档**，全量转移会产生悬空指针。故冻结方式经确认**取 (a)：仅冻结已转移的数据契约 + 接入契约两份**——两份顶部加 🧊 冻结标记、SSOT 转至 `platform/docs/`，CLAUDE.md §1 SSOT 生命周期改为「部分冻结」、§2/§3 这两份的指向改到 `platform/`；其余 5 份（架构 / 执行计划 / 代码规范 / 工具注册表 / 工具门户）尚无 platform 等价物，仍活在 `规划/`。

27. **Phase 1 代码生成器改为仓库内本地生成器**：原机器闸门骨架预留 `datamodel-code-generator` + `json-schema-to-typescript`，但当前本地环境无全局 `uv`，`npx` 也会受离线缓存 / 网络影响。为保证 schema→模型生成在仓库内可重复执行，改为 `platform/tools/generate_contracts.py` 从 `event.schema.json` 同时生成 Pydantic v2 模型与 TS 类型；生成物仍落 `platform/shared/contracts/`，文件头标「自动生成，勿手改」，仍被 lint/类型检查排除。该决策不改变数据契约，只改变生成工具。

28. **新增 CHANGELOG，并与开发日志分工**：`开发日志.md` 继续作为过程流水，任何改动必写；`CHANGELOG.md` 作为阶段 / 发布摘要，只记录项目能力变化、部署/接入影响、破坏性变更和迁移事项。维护规则写入 CLAUDE.md，避免把两份日志互相复制。

29. **统一用户系统扩展到外部工具，但按 portal / direct 两类入口渐进接入**：不把「从平台门户进入」作为识别真人的唯一方式。入口分为 `portal`（从使用端门户打开，平台注入短期身份）与 `direct`（用户直接打开工具，但工具接入平台 Auth API / SDK 后自行完成统一登录并上报可信身份）；识别不了身份时仍记 `anonymous`，不阻断入库。为避免过早升事件契约，Phase 2 先把 `entry_source` / `auth_method` 放进 `metadata`；等 SDK + demo + 一个低风险真实工具验证稳定后，再决定是否升 schema v0.3，把入口来源转成正式字段。真实工具接入顺序改为：真实数据库冒烟 → SDK + demo 工具 → 统一 Auth API 最小版 → 低风险真实工具试点。

30. **`规划/` 全量搬入 `platform/docs/`，规划目录退役（决策 #26 的 (a) 升级为全量）**：原决策 #26 只部分冻结（数据契约 / 接入契约转 platform，其余 5 份留 `规划/`），形成「两份看 platform、五份看规划」的双轨状态，对长期维护与交接是认知负担。本轮按用户「要标准、可交接」的要求，把剩余 5 份（架构与原则 → architecture.md、执行计划 → execution-plan.md、代码规范 → code-standards.md、工具注册表 → registry.md、工具门户 → portal.md）也搬入 `platform/docs/`（统一英文文件名），并删除已退役的 `规划/`（含两份冻结归档，其真源早已在 platform）。此后只有一个 SSOT 位置 `platform/docs/`，不再区分规划 / platform。所有跨文档链接同步重定向。

31. **`POST /auth/users` 收紧为需 admin token，首个 admin 由 seed 脚本引导**：内网威胁模型下「不做写入侧鉴权」只适用于事件上报（#7），但账号体系是读取侧权限（谁能看原文）的挂靠点（#17）。原端点完全开放且可直接造 admin，等于任何能访问 API 的人都能给自己开 admin、架空将来的读取侧分级。故创建用户改为需 admin token；首个 admin 无法经端点创建，由运维用 DB 凭据离线跑 `platform/tools/seed_admin.py` 引导。

32. **`tool_id` 发放通道＝管理员 API，命名规则定稿 `<team>-<tool>`**：原 `tool_id` 只能由平台方手工 `INSERT`（注册表无任何发放入口），是多方协作「第一公里」的断点；命名规则也一直「待团队端确认」。本轮拍板：① **形态取管理员 API**（`POST /registry/tools`）而非离线 CLkI——平台已有 FastAPI + admin 门禁（#31），注册走同一套 REST + 鉴权才是工程规范，且不必把 DB 凭据散给各团队（离线 seed 脚本只用于引导首个 admin）；② **命名规则定稿** `<team>-<tool>`（全小写 kebab、≥2 段、正则 `^[a-z0-9]+(?:-[a-z0-9]+)+$`），格式由平台固定、段值由团队选取，不再各团队各立规则；机器源 `platform/backend/storage/registry.py` 的 `TOOL_ID_REGEX`，发放通道用它自动校验（非法 422、重复 409）。本通道 MVP 只发**接入字段**，门户展示字段后续再设。注册表不属事件 `schema_version`，本决策不升事件契约版本。

33. **字段治理＝三层模型，metadata 带约定、按信号晋升为主表列**：解决「接入方要记没预置的字段时怎么办、metadata 会不会乱、长期能不能管」。定三层：① **主表统一字段**（圈一/二/三）平台定、横向可比、改它＝升 schema 版本（重）；② **metadata 语义约定** 平台定形状、接入方申请、放 metadata，加约定只改约定文档、**不升事件契约版本**（轻）；③ 纯一次性 metadata 工具自填。关键厘清：「**要不要记**」取决于有没有用（与频率无关，有用就全记）、「**记在哪**」才看频率（高频进列、低频留 metadata），**「不晋升」≠「不记录」**——留 metadata 照样完整持久可查。晋升（metadata→列）按**信号触发**（同类第 3 个工具又申请 / JSONB 分析费劲），非定期开会；晋升对接入方透明（平台从 metadata 映射进列，老工具不改），难点在历史脏数据，故立**打字规则**（snake_case、时间用 number 毫秒、二进制只存引用不入库、原文走主字段受敏感策略）保证将来好搬家。SSOT 落 `platform/docs/metadata-conventions.md`。其中「metadata 不合约定是否记告警」仍**待人工确认**；敏感内容策略见决策 #34。

34. **放开原文记录，读取侧权限留占位**：原「首轮不记原文」把两层顾虑搅在一起——写入侧（谁发、会不会乱塞）与读取侧（多用户上看板谁能看原文）。本平台唯一接入方就是平台方本人、内部局域网、写入侧本就不做鉴权（#7），故拍板：**`input_content` / `output_content` 现阶段允许记录原文，写入侧不设门禁**，始终不阻断入库。仅保留两处占位仍待人工确认：① **读取侧可见范围**——多用户上看板后按用户账号表角色分级（挂靠 #17），现阶段单人不设限；② **留存策略**（原文存多久 / 转摘要 / 删除）随服务器部署再定（#8）。本决策只放开 prose 策略、不改字段（`input_content`/`output_content` 早在 #20 已是通用选填），**不升事件契约版本**；连带改 schema.md / integration-guide.md / metadata-conventions.md / contract.md / execution-plan.md / 试点模板，并重跑 `export_integration_kit.py` 重生成分发包。

35. **迁移执行器＝仓库内最小幂等脚本，不引 Alembic**：原存储层只有建表 SQL、没有「按顺序应用」的机制——`0001_init.sql` 仅靠 docker `initdb` 在**首次空库**时执行，`0002+` 永不自动生效。这与本平台核心设计「schema 按 `schema_version` 演进、metadata 字段按信号晋升为主表列」（决策 #33）正面冲突：真到第一次加列/晋升时，改动落不到真实库。本轮补上执行器。**选型取舍**：① 不引 Alembic——它带 autogenerate / 模型反射 / 分支合并等重特性，而本项目迁移是「手写 SQL 文件按编号顺序应用」的简单场景，且本机离线、依赖可复现尚是欠账（execution-plan §五），多一个重依赖与「最小改动」相悖（同决策 #27 的离线务实路线）；② 取**仓库内最小脚本** `tools/migrate.py` + 纯逻辑 `backend/storage/migrate.py`（找文件/数字排序/去重/算待办，已单测覆盖）+ `schema_migrations` 跟踪表，每张迁移连同登记同事务、幂等可重跑。**旧库**（表已由 initdb 建过）需先「基线」一次（手工 `INSERT schema_migrations`），全新库直接跑。docker `initdb` 仍管全新容器首启，升级一律走执行器。本决策只加工具、不改数据契约，**不升事件契约版本**。将来若迁移复杂度上升，可再评估换 Alembic（走决策记录）。

---

## 下一步

**Phase 1.5 真实数据库冒烟已通过、`tool_id` 发放通道已实现**：在 Phase 2A/2B 闭环上，已在本机用免安装 PostgreSQL 16 真实跑通 `模拟 JSON → /events → usage_event` 落库 + 幂等（详见开发日志），并新增管理员发放通道 `POST /registry/tools`（决策 #32）。全套机器闸门在本机真实跑绿（决策 #32 实现 + 此前修复的 mypy 生成器红灯）。

- 进入 **Phase 2C 真实工具试点**：挑一个低风险、可改代码的真实工具，先经发放通道领 `tool_id`，复制 `platform/integrations/_template`，记圈一 + token + status + duration + 入口来源；原文 `input_content`/`output_content` 可按需记录（已放开，决策 #34，读取侧权限待定）。
- **Phase 2.5 接入工程化**剩余两项：自助契约校验 CLI（`tools/validate_payload.py`）、接入层连接池（`psycopg_pool`，放量前、需联网装依赖）。
- 试点稳定后再评估 **Phase 2D relay**（设计稿待确认）与 schema v0.3：`entry_source` / `auth_method` 暂继续放在 `metadata`。
- 真实 TCP 服务（uvicorn）那一跳本机跑不了（无 uvicorn + PyPI 被墙），到能联网 / 有 uvicorn 的机器按 `smoke.md` 原样补跑一次。
