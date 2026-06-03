# migrations —— 建表 SQL（占位，Phase 1）

三张共享表：统一事件表（含全部三圈字段，metadata=JSONB，在 tool_id/conversation_id/start_time/status 建索引）、工具注册表、用户账号表（密码只存哈希）。不预建价格表。现为占位。
