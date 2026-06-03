-- 0001_init.sql —— Phase 1 存储层初始建表（共享层三张表）
-- 契约版本：v0.2。字段语义见 platform/docs/schema.md，机器源见 platform/shared/schema/event.schema.json。
-- 三者必须一致：改字段需同步本文件 + schema.md + event.schema.json，并升 schema_version。
-- 目标库：PostgreSQL（metadata 用 JSONB）。本文件是建表 DDL，不含业务逻辑。

-- =====================================================================
-- 表一：统一事件表 usage_event —— 每一次工具使用 = 一条记录
-- =====================================================================
CREATE TABLE IF NOT EXISTS usage_event (
    -- 圈一：公共字段（硬性必填）
    record_id        UUID         PRIMARY KEY,                     -- 客户端生成，幂等去重靠它
    schema_version   TEXT         NOT NULL,                        -- 本条遵循的契约版本（如 v0.2）
    tool_id          TEXT         NOT NULL,                        -- 平台分配的固定 ID（FK → tool_registry）
    conversation_id  TEXT         NOT NULL,                        -- 「一次使用」聚合键
    start_time       TIMESTAMPTZ  NOT NULL,                        -- 调用开始（UTC）
    end_time         TIMESTAMPTZ  NOT NULL,                        -- 调用结束（UTC）
    duration_ms      INTEGER      NOT NULL CHECK (duration_ms >= 0),
    status           TEXT         NOT NULL CHECK (status IN ('success', 'failed', 'timeout')),
    ingested_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),          -- 服务端写入，区别于事件时间

    -- 圈二：LLM 专属（非 LLM 工具留 NULL）
    model            TEXT,
    prompt_tokens    INTEGER      CHECK (prompt_tokens     IS NULL OR prompt_tokens     >= 0),
    completion_tokens INTEGER     CHECK (completion_tokens IS NULL OR completion_tokens >= 0),
    total_tokens     INTEGER      CHECK (total_tokens      IS NULL OR total_tokens      >= 0),
    cost             NUMERIC(20, 8) CHECK (cost IS NULL OR cost >= 0),  -- 金额换算后置；本阶段以 token 计数为主
    cost_source      TEXT         CHECK (cost_source IS NULL OR cost_source IN ('source', 'computed')),

    -- 圈三：弹性选填
    user_id          TEXT,                                         -- 门户注入，否则匿名（绝不因拿不到人而拒收）
    team_id          TEXT,
    result_quality   REAL,                                         -- 质量信号（float），enum 形态走 metadata
    adopted          BOOLEAN,
    input_content    TEXT,                                         -- 通用选填，受敏感策略约束（待人工确认）
    output_content   TEXT,
    metadata         JSONB        NOT NULL DEFAULT '{}'::jsonb     -- 自由口袋：缓存/推理 token 等明细塞这里
);

-- 索引（交接命令指定：tool_id / conversation_id / start_time / status）
CREATE INDEX IF NOT EXISTS idx_usage_event_tool_id         ON usage_event (tool_id);
CREATE INDEX IF NOT EXISTS idx_usage_event_conversation_id ON usage_event (conversation_id);
CREATE INDEX IF NOT EXISTS idx_usage_event_start_time      ON usage_event (start_time);
CREATE INDEX IF NOT EXISTS idx_usage_event_status          ON usage_event (status);

COMMENT ON TABLE  usage_event IS '统一事件表：每一次工具使用一条记录。契约 v0.2，见 platform/docs/schema.md';
COMMENT ON COLUMN usage_event.conversation_id IS '「一次使用」聚合键，由工具按触发点自定义';
COMMENT ON COLUMN usage_event.cost_source IS 'source=源头返回 / computed=分析层按价表算';

-- 价格表：本轮不建。token→金额换算后置，需一张带生效时间的价格表
-- （每个 model 价格带 effective_from/effective_to），后续阶段再定。此处仅留位说明。

-- =====================================================================
-- 表二：工具注册表 tool_registry —— tool_id 来源 + 门户展示底表（两端共读）
-- =====================================================================
CREATE TABLE IF NOT EXISTS tool_registry (
    -- 接入字段（数据端用）
    tool_id        TEXT         PRIMARY KEY,                       -- 平台分配的固定 ID，两端共用主键
    name           TEXT         NOT NULL,                          -- 内部标识名
    team_id        TEXT,                                           -- 归属团队
    data_level     TEXT         NOT NULL DEFAULT 'minimal'
                                CHECK (data_level IN ('full', 'partial', 'minimal')),
    collect_method TEXT         NOT NULL DEFAULT 'report'
                                CHECK (collect_method IN ('report', 'relay', 'key')),
    model_default  TEXT,                                           -- 主要使用的模型（可空）

    -- 展示字段（使用端门户用，决策 #23/#25）
    category       TEXT,                                           -- 分类（门户按此分组卡片）
    display_name   TEXT,                                           -- 展示名（区别于内部 name）
    description    TEXT,                                           -- 简介（卡片说明 + AI 推荐语义匹配依据）
    icon           TEXT,                                           -- 小图标（标题行/紧凑列表/AI 推荐结果）
    thumbnail      TEXT,                                           -- 功能缩略图 URL/路径，占卡片主体；缺图门户自动生成占位
    launch_url     TEXT,                                           -- 局域网链接，门户「打开工具」跳转目标（注入 user_id）
    sort_weight    INTEGER      NOT NULL DEFAULT 0,                -- 默认排序权重（无偏好/无使用记录时兜底）
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE,             -- 是否在门户上架

    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tool_registry_category ON tool_registry (category);
CREATE INDEX IF NOT EXISTS idx_tool_registry_enabled  ON tool_registry (enabled);

COMMENT ON TABLE tool_registry IS '工具注册表：tool_id 来源 + 门户展示底表，数据端/使用端共读。改本表字段不升事件契约版本。';

-- =====================================================================
-- 表三：用户账号表 user_account —— user_id 来源 + 读取侧权限挂靠点
-- =====================================================================
CREATE TABLE IF NOT EXISTS user_account (
    user_id        TEXT         PRIMARY KEY,                       -- 事件表 user_id 的来源
    username       TEXT         NOT NULL UNIQUE,                   -- 登录账号
    password_hash  TEXT         NOT NULL,                          -- 只存哈希，绝不存明文（内网威胁模型）
    team_id        TEXT,                                           -- 所属团队
    role           TEXT         NOT NULL DEFAULT 'user'
                                CHECK (role IN ('admin', 'user')), -- 读取侧权限挂靠点；细则待人工确认
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_account_team_id ON user_account (team_id);

COMMENT ON TABLE user_account IS '用户账号表：一人一号，管理员发放、用户自改，库内存哈希不存明文。管「人」(user_id)，与 tool_registry 管「工具」分工。';
