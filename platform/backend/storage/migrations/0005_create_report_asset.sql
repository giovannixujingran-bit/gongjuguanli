CREATE TABLE IF NOT EXISTS report_asset (
    asset_id      UUID        PRIMARY KEY,
    asset_type    TEXT        NOT NULL DEFAULT 'ai_report'
                              CHECK (asset_type = 'ai_report'),
    filename      TEXT        NOT NULL,
    title         TEXT        NOT NULL,
    tool_id       TEXT        NOT NULL,
    tool_name     TEXT        NOT NULL,
    period_start  DATE        NOT NULL,
    period_end    DATE        NOT NULL,
    html          TEXT        NOT NULL,
    created_by    TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_asset_created_at ON report_asset (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_asset_tool_id ON report_asset (tool_id);

COMMENT ON TABLE report_asset IS 'AI 生成报告资产表：保存可预览、可下载的 HTML 报告。';
