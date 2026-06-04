# sdk —— 参考 SDK（Phase 2A）

工具自报的便捷封装（主路）：包装调用/触发点，归一化 token、写入入口来源、异步上报。**带本地缓冲 + 重试队列**，靠 `record_id` 幂等去重，避免「最该记时丢数据」。

入口来源先放入 `metadata`：

- `portal`：从使用端门户打开。
- `direct`：用户直接打开工具，但工具接入统一 Auth API / SDK。
- `unknown`：无法识别来源或身份，`user_id` 兜底为 `anonymous`。

## demo

```powershell
cd platform
python -m collection.sdk.demo_tool --endpoint-url http://127.0.0.1:8000/events --entry-source direct
python -m collection.sdk.demo_tool --endpoint-url http://127.0.0.1:8000/events --entry-source portal --auth-token <token>
python -m collection.sdk.demo_tool --endpoint-url http://127.0.0.1:8000/events --entry-source unknown
```

有 `--auth-token` 时，SDK 会加 `Authorization: Bearer <token>`，由平台校验并解析 `user_id` / `team_id`。
没有 token 时仍可上报，后端按契约兜底为 `anonymous`。
