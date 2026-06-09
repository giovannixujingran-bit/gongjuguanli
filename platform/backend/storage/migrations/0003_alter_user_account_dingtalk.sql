-- 0003_alter_user_account_dingtalk.sql —— 钉钉组织同步：账号关联钉钉身份 + 人↔部门关系（决策 #38）
-- 数据模型见 platform/docs/dingtalk-钉钉组织与部门治理/data-model-数据模型.md §三。
-- 钉钉免登成为唯一登录、密码体系退役（决策 #38/P2）：故 password_hash 改为可空，
-- 由钉钉同步建的账号不带密码；首个 admin 由 seed 脚本绑定 dingtalk_userid 引导。
-- 本迁移只动账号体系 + 新关系表，不改事件 schema、不升 schema_version。
-- 目标库：PostgreSQL。

-- 1) 账号表：加钉钉身份关联键；密码改为可空（P2 密码退役第一步）
ALTER TABLE user_account ADD COLUMN IF NOT EXISTS dingtalk_userid TEXT;
ALTER TABLE user_account ALTER COLUMN password_hash DROP NOT NULL;

-- dingtalk_userid 唯一（可空）：免登拿到的钉钉 userid 凭此映射到平台账号
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_account_dingtalk_userid
    ON user_account (dingtalk_userid)
    WHERE dingtalk_userid IS NOT NULL;

COMMENT ON COLUMN user_account.dingtalk_userid IS '钉钉员工唯一标识（userid）。免登据此映射到平台账号。决策 #38。';
COMMENT ON COLUMN user_account.password_hash IS '密码哈希（可空）。钉钉免登为唯一登录后，同步建的账号不带密码（P2 密码退役）。';

-- 2) 人↔部门关系（一人可属多部门，故用关联表）
CREATE TABLE IF NOT EXISTS user_department (
    user_id     TEXT         NOT NULL REFERENCES user_account (user_id) ON DELETE CASCADE,
    dept_id     BIGINT       NOT NULL REFERENCES department   (dept_id) ON DELETE CASCADE,
    is_primary  BOOLEAN      NOT NULL DEFAULT FALSE,            -- 是否钉钉「主部门」
    PRIMARY KEY (user_id, dept_id)
);

CREATE INDEX IF NOT EXISTS idx_user_department_dept_id ON user_department (dept_id);

COMMENT ON TABLE user_department IS '人↔部门关系：一人可属多部门。同步时按钉钉归属整体覆盖。决策 #38。';
