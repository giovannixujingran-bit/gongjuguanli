-- 0004_alter_user_account_display_name.sql —— 账号加显示名（钉钉同步用，决策 #38）
-- 钉钉同步的账号 username 取 dingtalk_userid（保证唯一、满足约束），人的真实姓名存这里。
-- 本迁移只加一列，不改事件 schema、不升 schema_version。

ALTER TABLE user_account ADD COLUMN IF NOT EXISTS display_name TEXT;

COMMENT ON COLUMN user_account.display_name IS '显示名（人的真实姓名）。钉钉同步账号的 username 取 dingtalk_userid，姓名存此列。';
