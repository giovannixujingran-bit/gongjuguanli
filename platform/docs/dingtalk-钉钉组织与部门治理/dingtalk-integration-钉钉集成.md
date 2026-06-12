# 钉钉集成（Phase A · 已实现，免登待真机验证）

> 本分册定义**钉钉打通**：一个企业内部应用，支撑「组织同步」+「免登认人」两件事。
> 总览见 [README](README-总览与索引.md)；数据结构见 [数据模型](data-model-数据模型.md)；关联决策 **#38/#47**。
> **当前状态**：组织同步已通过 `backend/org_sync` + `tools/sync_dingtalk.py` 落地；免登数据门禁已通过决策 #47 落地到 `/auth/dingtalk`、`/auth/config` 与前台钉钉 JSAPI，真实钉钉客户端登录仍待用户验证。

---

## 一、一个钉钉应用，干两件事

在钉钉管理后台创建**一个「企业内部应用」**，拿到一对凭据（AppKey / AppSecret，新版称 Client ID / Client Secret）。同一套凭据支撑：

| 能力 | 用户可见？ | 机制 |
|---|---|---|
| ① 组织同步 | 否（后台） | 平台用凭据换 `access_token`，调通讯录 API 拉部门树 + 人员，写入自己库 |
| ② 免登认人 | 是（前台） | 门户做成 H5 微应用挂工作台，员工点开时前端拿 `authCode`、后端换 `userid` |

> **H5 微应用**＝挂在钉钉工作台里的一个网页（钉钉用内置浏览器打开它）。因为跑在钉钉里，它能直接借用钉钉已登录的身份认出当前是谁——这正是「免登」的由来。
> **authCode**＝钉钉发的一张一次性临时凭证（5 分钟有效），本身不是身份，是「拿去换身份的票根」：前端拿到 `authCode`，后端拿它向钉钉换出真正的员工编号 `userid`。

**应用配置要点**：
- 授予**通讯录读权限**（获取部门列表 / 部门用户 / 用户详情）。
- 配置 H5 微应用**首页地址**＝内网门户 URL；加入工作台。
- 凭据走**配置 / 环境变量，零硬编码**（呼应 [代码规范](../code-standards-代码规范.md) §七、决策 #34 的密钥纪律）。

---

## 二、部署前置与约束（必须先满足）

| 项 | 要求 | 说明 |
|---|---|---|
| 服务器出网 | 平台服务器能**主动外呼**钉钉云（`https://oapi.dingtalk.com` / `https://api.dingtalk.com`） | 组织同步、用 `authCode` 换 `userid` 都是平台→钉钉云的出站请求；钉钉**不需要**回调你内网 |
| 门户可达性 | 门户 URL 要让**钉钉客户端访问得到** | **只在公司网络内用 PC 钉钉**——内网地址即可达（决策 #38 / P5）。手机 / 外网用需穿透 / 反代，后续再评估 |
| 凭据保管 | AppKey / AppSecret / `access_token` 不入库明文、不进日志、不硬编码 | 泄露即可读全公司通讯录 |

> 与现有架构「全部组件部署在局域网内」（[架构 §三](../architecture-架构与原则.md)）的关系：唯一新增的外部依赖是「平台服务器出站访问钉钉云」，门户与数据仍在内网；这不违背「采集点不绑外部依赖」原则（决策 #7 针对的是采集中转站，组织同步是读取侧的独立能力）。

---

## 三、组织同步服务

放在共享后端新模块 **`backend/org_sync`**（纯逻辑可单测，遵守单向依赖分层，[代码规范](../code-standards-代码规范.md)）；触发入口＝管理员 API 端点或 CLI（如 `tools/sync_dingtalk.py`）。

> **用 httpx 直调经典通讯录接口（决策 #39）**：实测官方新 SDK（`alibabacloud_dingtalk`，api.dingtalk.com）**不覆盖**部门树遍历所需的经典接口（`department/listsub`、`user/listid`），且拖来 ~30 个传递依赖。这些接口是 oapi.dingtalk.com 的 topapi，用仓库已有的 `httpx` 直调最简。钉钉调用藏在 `DingtalkClient` 抽象后（`HttpxDingtalkClient` 实现 + token 缓存），将来若需要可换实现。

### 3.1 流程

1. **取 `access_token`**：用凭据调 `/gettoken` 换 token；**缓存复用**（有效期约 7200s / 2h），过期前刷新，**不可频繁刷**（钉钉限频）。
2. **递归拉部门树**：从根 `dept_id = 1` 起，调「获取子部门列表」**逐层**拿下一级子部门——钉钉接口**一次只返回下一级**，必须按 `parent_id` 循环 / 递归才能建整棵树。
3. **拉部门人员**：每个部门调「获取部门用户 userid 列表」拿 `userid`，再「获取用户详情」拿 `name` / 主部门等。
4. **upsert**（有则更新、无则插入的合并写入）：写 `department`（部门树）、`user_account.dingtalk_userid`（人）、`user_department`（人↔部门）。详见 [数据模型](data-model-数据模型.md)。
5. **失活本轮未见的**：钉钉已删的部门 / 已变更的归属，按软删处理（`department.active = false`，归属删除），不硬删（决策 #38 / P6）。
6. **记 `synced_at`**。

### 3.2 频率与兜底

| 项 | 设计 |
|---|---|
| 频率 | **每小时一次定时 + 管理员手动触发端点**（决策 #38 / P1） |
| 幂等 | 整个同步是「覆盖式 upsert」，可重复跑、跑几次结果都一样（这就是「幂等」：重复执行不会产生额外副作用） |
| 失败兜底 | 钉钉接口失败 / 限流 → 本轮中止、**保留上轮数据**（同步失败不破坏现状）；`access_token` 失效自动重取 |
| 安全 | 凭据 / token 只在内存与配置中，不落库不进日志 |

---

## 四、免登流程

门户做成 H5 微应用，在 **PC 钉钉**内打开（本轮约束）。

1. **前端拿 `authCode`**：门户页引 `dingtalk-jsapi`，调 `dd.runtime.permission.requestAuthCode({ corpId })` → `authCode`（**5 分钟有效、一次性**）。
2. **前端提交**：`POST /auth/dingtalk { code }`（已实现端点）。
3. **后端换 `userid`**：用缓存的 `access_token` + `authCode` 调钉钉「根据 code 获取用户信息」→ 得 `userid`。
4. **映射到平台账号**：按 `userid` 查 `user_account.dingtalk_userid` → 得 `user_id` → 签发平台会话 / token。
5. **找不到账号**（同步尚未覆盖的新员工）：设计目标是即时拉一次该 `userid` 的用户详情 + 主部门，当场 upsert 建账号再登入（决策 #38 / P3）。当前已实现链路先返回「账号未同步，请联系超管」，即时补拉仍待实现。

### 与现有入口 / 身份模型的衔接（决策 #29）

- `entry_source = portal`（员工从门户入口进）。
- `auth_method` 新增取值 **`dingtalk_sso`**——按决策 #29，先放进 `metadata`（[metadata 约定](../metadata-conventions-metadata约定与字段治理.md) 加一条约定值），**暂不升 schema**；稳定后再评估是否随 v0.3 转正式字段。
- 接不进的场景仍记 `anonymous`，不阻断（决策 #18/#29 口径不变）。

---

## 五、管理员（admin）认定

免登世界里「谁是 admin」：

- **超管**：钉钉 `userid` 命中配置 `BOOTSTRAP_ADMIN_DINGTALK_USERID` 即为超管；超管可看数据端，也可增减普通 admin（决策 #47）。
- **admin**：复用现有用户账号表的 `role='admin'` 标记，通过 `dingtalk_userid` 关联到具体钉钉人；admin 可看数据端，不能增减 admin。
- **首个超管引导**：密码登录已退役（P2），首个超管由环境变量配置认定，取代旧 `tools/seed_admin.py` 离线引导。`seed_admin.py` 若保留，只能视作遗留/普通 admin 辅助，不再作为超管来源。

---

## 六、密码体系的去留

- 钉钉免登成为**唯一登录**，现有「管理员发密码 + 哈希存储」（决策 #17/#31）登录路径**完全退役**（决策 #38 / P2 / #47）：`/auth/login` 与前台密码框已删除。
- 受影响项：① 首个超管由 `BOOTSTRAP_ADMIN_DINGTALK_USERID` 配置认定；② `user_account.password_hash` 列暂留可空，是否删列后置；③ `/auth/users` 仍作为 admin 门禁下的账号维护接口保留。
- 决策 #17/#31 的密码登录部分由 #47 取代；当前正文以 [架构 §五](../architecture-架构与原则.md) 为准。

---

## 七、开发期工具链（SDK / MCP）

钉钉开发生态**能力中上、DX 偏糙**（文档中文优先、新旧 API 双轨、无现成「组织管理 CLI」），但官方提供了足够的程序化入口，**开发期可大量交给模型/脚本驱动**：

| 开发动作 | 用什么 | 说明 |
|---|---|---|
| 边开发边探接口（实拉一次部门树、看字段、验权限） | **官方钉钉 MCP**（`open-dingtalk/dingtalk-mcp`，含 `dingtalk-contacts` / `dingtalk-department` 等模块） | 本地用 `Client ID/Secret` + `ACTIVE_PROFILES` 启动，把 Claude Code 指过去，让模型**真调一次**看结果，替代「啃文档猜」 |
| 写同步代码 | **httpx 直调 topapi** | 见 §三，藏在 `DingtalkClient` 抽象后（决策 #39，官方新 SDK 不覆盖部门树遍历） |
| 喂接口规格给模型生成代码 | OpenAPI / Apifox 文档 | —— |

- **唯一手工环节**：钉钉后台建内部应用、拿凭据、授通讯录权限（一次性，安全边界，无 CLI）。
- ⚠️ 开发期 MCP 连的是**真实公司通讯录**，凭据按敏感信息管、用最小权限，别让模型乱写（与 §二凭据保管、决策 #34 密钥纪律一致）。

> 这层是**开发期辅助**，不是运行期依赖：上线后组织同步由 `backend/org_sync` 用 httpx 自动跑，不依赖 MCP。

---

## 八、实现顺序（Phase A 内部）

1. 钉钉应用申请 + 凭据配置 + 部署前置确认（出网、门户内网可达）。
2. `backend/org_sync` 同步服务（token 缓存 → 递归拉树 → 拉人员 → upsert）+ 部门 / 账号仓库扩展 + 迁移（见 [数据模型](data-model-数据模型.md) §六）。
3. `POST /auth/dingtalk` 免登端点 + 门户前端 `requestAuthCode` 接入。
4. 超管 / admin 认定衔接 + `auth_method=dingtalk_sso` 进 metadata。
5. 机器闸门全绿（[代码规范](../code-standards-代码规范.md)），开发日志追加。

Phase A 通后再做 [Phase B 可见性治理](visibility-governance-部门化可见性治理.md)。
