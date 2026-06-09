-- 0002_create_department.sql —— 钉钉组织同步：部门表（设计稿 Phase A，决策 #38）
-- 钉钉部门树的只读镜像，钉钉为唯一源（平台侧不手工增改）。
-- 数据模型见 platform/docs/dingtalk-钉钉组织与部门治理/data-model-数据模型.md §二。
-- 本迁移只加注册表/账号体系之外的新表，不改事件 schema、不升 schema_version。
-- 目标库：PostgreSQL。

CREATE TABLE IF NOT EXISTS department (
    dept_id      BIGINT       PRIMARY KEY,                       -- 钉钉部门 id（根部门固定为 1）
    parent_id    BIGINT,                                        -- 上级部门 dept_id；根部门为空
    name         TEXT         NOT NULL,                          -- 部门名
    source       TEXT         NOT NULL DEFAULT 'dingtalk',       -- 来源标记（预留多源可能）
    active       BOOLEAN      NOT NULL DEFAULT TRUE,             -- 钉钉已删除的部门置 false（软删，决策 #38/P6）
    synced_at    TIMESTAMPTZ,                                    -- 最近一次同步写入时间
    dingtalk_raw JSONB                                           -- 钉钉原始字段留档（可选，便于排查/扩展）
);

CREATE INDEX IF NOT EXISTS idx_department_parent_id ON department (parent_id);
CREATE INDEX IF NOT EXISTS idx_department_active    ON department (active);

COMMENT ON TABLE  department IS '部门表：钉钉部门树的只读镜像，钉钉为唯一源。软删保留（active=false），不硬删。决策 #38。';
COMMENT ON COLUMN department.parent_id IS '自指 dept_id 构成部门树；门户「向下级联」可见性判定遍历此树。';
