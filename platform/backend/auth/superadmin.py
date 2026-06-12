from __future__ import annotations


def parse_superadmin_userids(raw: str | None) -> set[str]:
    """把逗号分隔的钉钉 userid 配置解析成集合，忽略空白项。

    超管 tier 只认配置（BOOTSTRAP_ADMIN_DINGTALK_USERID），UI 永不可改——
    天然只有超管能增减 admin（决策见 specs/2026-06-12-钉钉免登数据门禁-design.md §3）。
    """
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}
