# ingestion —— 接入 API（Phase 1）

统一上报 API：接收一条流水 → 进入即按 `event.schema.json` 生成的 Pydantic 模型校验契约 → 落库。不合规当场打回。

- `GET /health`：健康检查。
- `POST /events`：接收模拟或真实事件 JSON；圈一缺失返回 422；`user_id` 缺失时补 `anonymous`；按 `record_id` 幂等写入 `usage_event`。
- `DATABASE_URL` 从环境变量读取，零硬编码。
