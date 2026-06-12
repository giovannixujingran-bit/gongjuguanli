# auth —— 账号体系（钉钉免登 + 角色门禁）

账号由钉钉组织同步建立（无密码，按 `dingtalk_userid` 唯一），是 `user_id` 的来源，也是读取侧权限的挂靠点。身份认证走**钉钉免登**，不再有密码登录（决策 #38/#44，P2 密码退役）。见 [架构-入口门户与账号体系](../../docs/architecture-架构与原则.md)。

## 三层角色

- **超管**：钉钉 userid ∈ 配置 `BOOTSTRAP_ADMIN_DINGTALK_USERID`（逗号分隔，UI 不可改）。看数据端 + 增减 admin。
- **admin**：超管在面板里设的（DB `user_account.role='admin'`）。看数据端，但不能增减 admin。
- **普通员工**：组织同步进来的其他人。只用工具 + 看自己历史；统计/明细不可见。

判定口径：`can_view_data` = `role=='admin' 或 is_superadmin`；`can_manage_admins` = `is_superadmin`。超管隐含 admin 待遇（token 签发为 `role='admin'` 且 `is_superadmin=True`）。

## Auth API

- `POST /auth/dingtalk { code }`：钉钉免登 code → `user/getuserinfo` 换 userid → 查已同步账号 → 签发短期 Bearer token（claims 带 `role` + `is_superadmin`）。未同步账号 403。
- `GET /auth/config`：下发前台免登所需的 `corp_id`（公开标识，不含 secret）。
- `GET /auth/admins`、`POST /auth/admins/{user_id}`：列员工 / 设撤 admin，**仅超管**。
- `POST /auth/verify`、`GET /auth/me`：校验 token / 读当前用户。
- `POST /auth/users`：创建用户（管理员动作，保留；组织同步为账号主来源）。

数据端读接口（`/analytics/*`、`/ai/query`）门禁为 `require_data_viewer`（admin 或超管）。

**首个 admin（超管）怎么来**：由配置 `BOOTSTRAP_ADMIN_DINGTALK_USERID` 指定的钉钉 userid，免登进来即超管——取代了旧的 `tools/seed_admin.py` 离线引导（后者只能标普通 admin、无法区分超管）。

`POST /events` 带合法 Bearer token 时，由平台解析 token 覆盖 payload 里的 `user_id` / `team_id`；没有 token 时仍允许入库，按契约兜底为 `anonymous`。部门/角色细粒度分级、预览脱敏仍待人工确认，后置实现。
