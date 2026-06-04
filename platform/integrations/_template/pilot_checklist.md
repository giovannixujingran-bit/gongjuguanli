# 真实工具试点清单

> 适用于 Phase 2C 的第一个真实工具。目标是验证真实业务路径能稳定上报，不追求一次接满所有字段。

## 试点准入

- 工具必须可改代码，或至少可在调用 LLM/API 的稳定入口加一层封装。
- 工具 owner 明确，试点期间允许快速回滚。
- 不接入会影响生产稳定性的核心链路；优先选低频、低风险、内部使用工具。
- 已在工具注册表登记并获得唯一 `tool_id`。
- 已准备测试账号，能区分 `portal` / `direct` / `unknown` 至少一种入口。

## 首轮采集范围

- 必填：`record_id`、`schema_version`、`tool_id`、`conversation_id`、`start_time`、`end_time`、`duration_ms`、`status`。
- 尽量填：`model`、`prompt_tokens`、`completion_tokens`、`total_tokens`、`user_id`、`team_id`。
- 必须放入 `metadata`（形状如下）：
  - `entry_source`：`portal` / `direct` / `unknown`（见 [metadata-conventions.md](../../docs/metadata-conventions.md) / 决策 #29）。
  - `auth_method`：身份获取方式，string，如 `session_token` / `bearer` / `none`。
  - `pilot_tool`：boolean，试点期填 `true`，标记本条为试点数据，便于分析层把试点 / 正式数据分开。
  - `integration_version`：string，埋点接入代码版本（semver，如 `1.0.0`），换埋点实现时递增，便于回溯哪一版产生的数据。
- 可按需记录：`input_content`、`output_content` 原文（已放开，读取侧可见范围待定，见 [schema.md](../../docs/schema.md) 敏感内容策略）。

## 接入方式

1. 优先使用 `collection.sdk.PlatformTracker` 直接上报。
2. 如果工具已经有自己的请求封装，在调用完成处构造 usage 事件。
3. 失败、超时也必须上报，`status` 分别填 `failed` / `timeout`。
4. 开启 SDK 本地 buffer，避免平台短暂不可用时丢记录。**buffer 路径必须每工具独立**（建议含 `tool_id`，如 `.platform-buffer/<tool_id>.jsonl`）：同机多个工具共用同一 buffer 文件会互相覆盖。上报成功时 SDK 会自动重发积压在 buffer 里的记录（靠 `record_id` 幂等去重，不会重复落库）。
5. 用户从门户进入时使用 `entry_source=portal`；用户直接打开工具但登录同一账号系统时使用 `entry_source=direct`；无法识别时使用 `unknown` 并让后端落为 `anonymous`。

## 验收

- 本地或测试环境完成一次 `POST /events -> usage_event` 落库验证。
- 连续跑 1 天或至少 20 次试点调用，没有重复、漏记、阻塞用户操作的问题。
- 数据端能看到该工具的按 `tool_id` 聚合记录。
- 验证 `record_id` 幂等：重复上报不会重复落库。
- 验证匿名兜底：缺少身份时仍可入库。

## 回滚

- 工具侧保留一个环境变量开关，例如 `PLATFORM_TRACKING_ENABLED=false`。
- 回滚只关闭上报，不删除平台表结构，不改 schema。
- 回滚后在开发日志记录原因、影响范围、恢复条件。
