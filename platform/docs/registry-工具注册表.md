# 工具注册表（共享层）

> `tool_id` 的来源，也是使用端门户工具目录的底表——**两端共读的共享资产**。
> 字段定义配套见 [数据契约](schema-数据契约.md)；接入义务见 [接入契约](contract-接入契约.md)。

---

## 一、定位

`tool_id` 由平台**统一分配**：工具接入前先在注册表登记，平台发一个固定 ID，工具方用这个 ID 对接、每条记录回填。登记走**发放通道**（管理员 API，见下文 §三），登记成功即得到可用的 `tool_id`。

> **命名规则（已定稿，决策 #32）**：`tool_id` 用 `<team>-<tool>` 形式——**全小写 kebab-case，至少两段**，段内只含 `[a-z0-9]`，单连字符相连，无前后缀连字符、无双连字符。正则 `^[a-z0-9]+(?:-[a-z0-9]+)+$`（机器源在 `backend/storage/registry.py` 的 `TOOL_ID_REGEX`，发放通道用它自动校验，非法格式直接 422）。
>
> **格式由平台固定、段值由团队选取**：第一段是团队前缀（保证跨团队不撞、一眼看出归属），其后是工具名，可多段（如 `infra-log-exporter`）。各团队在此格式内自取段值，不再各立规则。示例 `smoke-demo-tool` 即合法。

这张表**同时服务两端**：

- **数据端**：接入管理页的底表，也是将来「价格表」与「读取侧权限（按工具分级）」的挂靠点。
- **使用端**：使用者门户的工具目录底表——分类、卡片展示、局域网链接、排序都读它（见 [使用端-工具门户](portal-工具门户.md)）。

> **与用户账号表分工**：用户账号表管「人」（`user_id`，见 [架构-入口门户与账号体系](architecture-架构与原则.md)）；本表管「工具」（`tool_id`）。

---

## 二、字段

分两组：**接入字段**（数据端采集用，原 v0.1 已有）与**展示字段**（使用端门户用，本轮新增，决策 #23）。

### 接入字段（数据端用）

| 字段 | 说明 |
|---|---|
| `tool_id` | 平台分配的固定 ID（主键，两端共用） |
| `name` | 工具名（内部标识） |
| `team_id` | 归属团队 |
| `data_level` | 数据粒度：full（token+用户+结果全有）/ partial / minimal（只到「哪个工具」） |
| `collect_method` | 采集方式：report（工具自报，主路；参考 SDK 为其封装）/ relay（转发兜底）/ key（独立 key 区分） |
| `model_default` | 主要使用的模型（可空） |

### 展示字段（使用端门户用）

| 字段 | 说明 |
|---|---|
| `category` | 分类（门户按此分组展示卡片） |
| `display_name` | 展示名（给使用者看，区别于内部 `name`） |
| `description` | 工具简介（卡片说明，也是 [AI 工具推荐](portal-工具门户.md) 的语义匹配依据） |
| `icon` | 小图标（用在标题行、紧凑列表、AI 推荐结果） |
| `thumbnail` | **功能缩略图**（图片 URL / 路径）：工具界面截图或效果图，占据门户卡片主体。选填，缺图时门户用「`icon` + `display_name` + 色块」自动生成占位图 |
| `launch_url` | 局域网链接（门户「打开工具」的跳转目标，打开时注入 `user_id`） |
| `sort_weight` | 默认排序权重（使用者无自定义偏好、又无使用记录时的兜底排序） |
| `enabled` | 是否在门户上架展示 |

> 展示字段不属于事件 `schema_version` 的范畴（那是事件表的契约），改本表字段不升事件契约版本。

---

## 三、发放通道

工具接入第一步＝拿 `tool_id`。发放走**管理员 API**（与 `/auth/users` 同一门禁，决策 #31/#32）：

| 项 | 说明 |
|---|---|
| 端点 | `POST /registry/tools` |
| 鉴权 | 需 **admin token**（非 admin 403、无 token 401）。首个 admin 由 `tools/seed_admin.py` 离线引导（见 [架构-账号体系](architecture-架构与原则.md)） |
| 请求体 | `tool_id`（必填，按上方命名规则校验）、`name`（必填）、`team_id` / `data_level` / `collect_method` / `model_default`（选填，缺省走建表默认 `minimal` / `report`） |
| 成功 | `201`，返回登记后的接入字段 |
| 重复登记 | `409`（`tool_id` 是主键，重复显式报错，不静默） |
| 非法 `tool_id` | `422`（命名规则由请求模型 `pattern` 自动校验） |

> **本通道只发接入字段**（让工具能尽快上报）。门户**展示字段**（`category`/`display_name`/`thumbnail` 等）后续由门户后台 / 更新接口设置，不在本端点 MVP 范围。
>
> 实现：接入层 `backend/ingestion/app.py` 的 `register_tool` + 存储层 `backend/storage/registry.py`（`PostgresToolRegistryRepository`，`INSERT ... ON CONFLICT (tool_id) DO NOTHING` 落 `tool_registry`）。
