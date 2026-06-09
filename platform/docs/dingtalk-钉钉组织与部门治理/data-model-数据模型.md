# 数据模型（设计稿 · 待实现）

> 本分册定义钉钉组织同步 + 部门化治理涉及的**全部数据结构**：三处改动 + 可见性判定算法 + 与现有结构的关系 + 迁移规划。
> 总览见 [README](README-总览与索引.md)；关联决策 **#38**。
> **不改事件 schema、不升 `schema_version`**（全是注册表 + 账号 + 新表）。

---

## 一、三处改动总览

| # | 改动 | 类型 | 跟现有的关系 |
|---|---|---|---|
| 1 | 新建 `department` 部门表 | 新表 | 全新；钉钉部门树的只读镜像，钉钉为 SSOT |
| 2 | 用户账号表加 `dingtalk_userid` + 新建 `user_department` | 扩展 + 新表 | 账号表仍管「人」；密码登录退役（P2），账号改由钉钉同步 + 免登维系 |
| 3 | `tool_registry` 加治理字段 + 新建 `tool_visible_department` | 扩展 + 新表 | `team_id`、`tool_id` 前缀**保留不动**；治理字段是新结构化外键 |

---

## 二、`department`（部门表）

钉钉部门树的只读镜像。钉钉部门 id 为整数，根部门 id 固定为 `1`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `dept_id` | bigint，主键 | 钉钉部门 id（根 = 1） |
| `parent_id` | bigint，可空 | 上级部门 `dept_id`；根部门为空 |
| `name` | text | 部门名 |
| `source` | text，默认 `'dingtalk'` | 来源标记（预留多源可能） |
| `active` | bool，默认 `true` | 钉钉已删除的部门置 `false`（**软删**，不硬删，避免 `tool_visible_department` / `user_department` 悬空引用，决策 #38 / P6） |
| `synced_at` | timestamptz | 最近一次同步写入时间 |
| `dingtalk_raw` | jsonb，可空 | 钉钉原始字段留档（可选，便于排查 / 将来扩展） |

- **建树**：`parent_id` 自指 `dept_id`。门户做「向下级联」可见性判定时需要遍历这棵树（见 §五）。
- **只读**：平台侧不手工增改部门，一切以同步为准（决策 #38：钉钉为唯一源）。

---

## 三、账号扩展 + `user_department`

### 3.1 用户账号表扩展

现有用户账号表是 `user_id` 的来源（[架构 §五](../architecture-架构与原则.md)，决策 #17）。新增一列：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `dingtalk_userid` | text，唯一，可空 | **关联键**：钉钉员工唯一标识（`userid`，钉钉侧生成后不可改）。免登拿到的 `userid` 凭此映射到平台账号 |

- 现有 `user_id` / 角色等字段**不动**；密码登录退役（P2），密码哈希列在实现时随迁移移除 / 废弃。
- `user_id` 来源不变（仍由账号表生成），只是**多了一条到钉钉身份的关联**：免登 → `dingtalk_userid` → 查到账号 → 得 `user_id`。
- **账号的来源**：组织同步覆盖全员时，会为每个钉钉 `userid` upsert 一条账号（见 [钉钉集成](dingtalk-integration-钉钉集成.md) §三）。免登时遇到尚未同步到的新员工＝**即时拉一次**当场建账号（决策 #38 / P3，见钉钉集成 §四）。

### 3.2 `user_department`（人↔部门，一人多部门）

钉钉允许一人属于多个部门，故用关联表而非账号表上的单列。

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_id` | FK → 用户账号表 | 平台用户 |
| `dept_id` | FK → `department` | 所属部门 |
| `is_primary` | bool，默认 `false` | 是否钉钉「主部门」 |

主键 `(user_id, dept_id)`。同步时按钉钉归属整体覆盖（本轮未见的归属删除或失活）。

---

## 四、`tool_registry` 治理字段 + `tool_visible_department`

### 4.1 注册表新增字段（**治理字段**，新的一组）

[工具注册表](../registry-工具注册表.md) 现有「接入字段」+「展示字段」两组，本设计加第三组**治理字段**（同样不属事件 `schema_version`）：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `owner_dept_id` | bigint，FK → `department`，可空 | 工具**归属部门**。默认可见性＝仅本部门（+ 子部门，见 §五） |
| `visible_to_all` | bool，默认 `false` | 公司级**公共工具**一键全开（免得把所有部门都列进白名单） |

> `visible_dept_ids`（额外白名单）的承载＝下面的 `tool_visible_department` 关联表，不在 `tool_registry` 上放 JSONB 数组（决策 #38 / P4）。

### 4.2 `tool_visible_department`（工具↔额外可见部门）

| 字段 | 类型 | 说明 |
|---|---|---|
| `tool_id` | FK → `tool_registry` | 工具 |
| `dept_id` | FK → `department` | **额外**获授可见的部门（在 `owner_dept_id` 之外） |

主键 `(tool_id, dept_id)`。**用关联表而非 JSONB 数组**（决策 #38 / P4）——「关联表」是单独一张「工具↔部门」对应表，一行一对；「JSONB 数组」则是把多个部门 id 塞进 `tool_registry` 某一列里当一个数组存（JSONB 是 PostgreSQL 存 JSON 的字段类型）。选前者，因为门户过滤是「按当前用户的部门集合 join 出可见工具」，关联表能直接 join、走索引；JSONB 数组要逐行拆开做包含判断，量大时不划算。

### 4.3 与现有 `team_id` / `tool_id` 的关系（**保留不动**）

| 现有 | 现状 | 本设计 |
|---|---|---|
| `tool_id` 的 `<team>-<tool>` 前缀（决策 #32） | 命名约定（字符串前缀） | **不动**，仍是命名规则 |
| `team_id`（自由字符串归属标记） | 注册表接入字段 | **不动**，与 `owner_dept_id` 并存；可在实现时提供「team_id → owner_dept_id」一次性映射辅助，但不强制改 `team_id` 语义 |

`owner_dept_id` 是新的**结构化外键**（指向真实钉钉部门树），跟上面两个自由字符串互不冲突。

---

## 五、可见性判定算法（门户取数核心）

> **先说人话**：规则是「开给父部门 = 连它下面的子部门一起开」。判断某人能不能看到某工具，最省力的办法是**从这个人的部门往上数到公司根**，把沿途每一级上级列成一串（比如「前端一组 → 前端组 → 研发中心 → 根」），这串里只要出现了工具被授权的部门，就可见。下面是正式表述。

给定登录用户的部门集合 `D`（其 `user_department` 里所有 `dept_id`），工具 `T` 对该用户**可见**当且仅当满足任一：

1. `T.visible_to_all = true`；或
2. 用户某部门 `d ∈ D` 落在「**授权部门或其任一子部门**」中——即存在授权部门 `g ∈ ({T.owner_dept_id} ∪ T 的 tool_visible_department)`，使得 `d == g` 或 `d` 是 `g` 的后代（**向下级联**：开给父部门＝含所有子部门）。

> **admin 例外**：admin 角色用户看**全部**工具（管理需要），不走上述过滤。

### 高效实现（推荐：用户部门取祖先链）

「开给父部门含子部门」等价于：把**用户的每个部门向上取祖先链闭包** `A`（含自身直到根），若 `A` 与「授权部门集合（owner ∪ 白名单）」相交，则可见。

> **祖先链闭包**＝从用户所在部门出发，顺着「上级」一层层往上数到公司根，把沿途每一级（含自己）都收进集合 `A`，比如 `A = {前端一组, 前端组, 研发中心, 根}`。「相交」就是看 `A` 里有没有出现工具授权的那个部门。

- 因为用户在子部门时，其祖先链含被授权的父部门 → 相交 → 可见。✓
- 比「把授权部门展开成整棵子树再比对」更省（祖先链是一条线，子树是一片）。

实现上可在门户加载时：① 查用户部门集合；② 用 `department.parent_id` 递归（PG `WITH RECURSIVE`：PostgreSQL 顺着每行记的「直接上级」自动一层层往上爬、一次查出整条祖先链）取祖先链闭包 `A`；③ `SELECT` 注册表，过滤 `visible_to_all OR owner_dept_id IN A OR EXISTS(tool_visible_department where dept_id IN A)`，再叠加现有 `enabled = true`（[门户](../portal-工具门户.md) §二）。

---

## 六、迁移文件规划

按 [迁移执行器](../execution-plan-执行计划与技术栈.md)（决策 #35：仓库内最小幂等脚本，按编号顺序应用），在 `platform/backend/storage/migrations/` 新增编号迁移（编号接现有最大值往后排）：

| 迁移（示意命名） | 内容 |
|---|---|
| `00NN_create_department.sql` | 建 `department` 表 |
| `00NN_alter_user_account_dingtalk.sql` | `user_account` 加 `dingtalk_userid` 列（唯一）；建 `user_department` 表 |
| `00NN_alter_tool_registry_visibility.sql` | `tool_registry` 加 `owner_dept_id` / `visible_to_all`；建 `tool_visible_department` 表 |

- 迁移幂等、可重跑（决策 #35）；旧库走执行器升级，全新库 initdb + 执行器。
- 存储层仓库类（如 `backend/storage/registry.py` / 账号仓库）相应扩展读写方法；新增部门仓库（如 `backend/storage/department.py`）。
- 不触发 schema→模型重生成（事件 schema 未变）。
