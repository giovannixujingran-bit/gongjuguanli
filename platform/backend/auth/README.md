# auth —— 账号体系（Phase 2B 最小版）

用户账号表与登录：一人一号、管理员发放、用户自改、库内**存哈希不存明文**。是 `user_id` 的来源，也是读取侧权限（按人分级，细则待定）的挂靠点。见 [架构-入口门户与账号体系](../../docs/architecture.md)。

当前已实现最小 Auth API：

- `POST /auth/users`：创建用户。**需 admin token**——账号体系是读取侧权限的挂靠点，必须挡住「局域网内任何人给自己开 admin」。
- `POST /auth/login`：账号密码登录并签发短期 Bearer token。
- `POST /auth/verify`：校验 token。
- `GET /auth/me`：读取当前 token 对应用户。

**首个 admin 怎么来**：`/auth/users` 要求调用者已是 admin，所以第一个 admin 无法经端点创建，
由运维用 DB 凭据离线跑一次 [`tools/seed_admin.py`](../../tools/seed_admin.py) 引导；之后所有账号都由
admin 登录后经 `/auth/users` 创建（落实架构文档「管理员发放初始账号密码」）。

`POST /events` 带合法 Bearer token 时，由平台解析 token 覆盖 payload 里的 `user_id` / `team_id`；
没有 token 时仍允许入库，并按契约兜底为 `anonymous`。登录前端、读取侧权限细则仍待人工确认，后置实现。
