from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Literal, Protocol
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.auth.accounts import (
    PostgresUserAccountRepository,
    Role,
    UserAccount,
    UserAccountRepository,
)
from backend.auth.superadmin import parse_superadmin_userids
from backend.auth.tokens import TokenClaims, bearer_token, issue_token, verify_token
from backend.ingestion.ai_query import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    AiQueryError,
    ApimartGeminiClient,
)
from backend.org_sync.client import HttpxDingtalkClient
from backend.storage.assets import (
    PostgresReportAssetRepository,
    ReportAsset,
    ReportAssetRepository,
)
from backend.storage.events import (
    PostgresUsageEventReader,
    PostgresUsageEventRepository,
    ReportMetricBreakdown,
    ReportPeriod,
    StoredEvent,
    ToolReportData,
    UsageEventReader,
    UsageEventRepository,
    UsageSummary,
)
from backend.storage.registry import (
    TOOL_ID_REGEX,
    CollectMethod,
    DataLevel,
    PostgresToolDirectory,
    PostgresToolRegistryRepository,
    ToolAlreadyExistsError,
    ToolConfig,
    ToolDirectory,
    ToolRegistration,
    ToolRegistryRepository,
)
from shared.contracts.event_model import UsageEvent
from shared.schema_version import SUPPORTED_SCHEMA_VERSIONS

logger = logging.getLogger(__name__)


class UserCreateRequest(BaseModel):
    username: str
    password: str
    user_id: str | None = None
    team_id: str | None = None
    role: Role = "user"


class UserPublic(BaseModel):
    user_id: str
    username: str
    team_id: str | None = None
    role: str
    is_superadmin: bool = False


class DingtalkLoginRequest(BaseModel):
    code: str = Field(min_length=1)


class AdminSummaryPublic(BaseModel):
    user_id: str
    dingtalk_userid: str | None = None
    display_name: str | None = None
    role: str


class SetRoleRequest(BaseModel):
    role: Role


class AuthConfigPublic(BaseModel):
    corp_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int
    user: UserPublic


class VerifyTokenRequest(BaseModel):
    token: str


class EventIngested(BaseModel):
    record_id: UUID
    ingested_at: datetime
    inserted: bool


class ToolRegisterRequest(BaseModel):
    # tool_id 命名规则在此自动校验（非法格式 → 422）；规则 SSOT 见 backend/storage/registry.py
    # 的 TOOL_ID_REGEX 与 platform/docs/registry-工具注册表.md。
    tool_id: str = Field(pattern=TOOL_ID_REGEX)
    name: str = Field(min_length=1)
    team_id: str | None = None
    data_level: DataLevel = "minimal"
    collect_method: CollectMethod = "report"
    model_default: str | None = None


class ToolPublic(BaseModel):
    tool_id: str
    name: str
    team_id: str | None = None
    data_level: str
    collect_method: str
    model_default: str | None = None


class ToolCardPublic(BaseModel):
    tool_id: str
    display_name: str
    category: str | None = None
    description: str | None = None
    icon: str | None = None
    thumbnail: str | None = None
    launch_url: str | None = None
    usage_count: int = 0


class EventRowPublic(BaseModel):
    record_id: UUID
    tool_id: str
    tool_name: str
    model: str | None = None
    user_id: str
    user_display_name: str | None = None
    chapter: str | None = None
    input_preview: str | None = None
    output_preview: str | None = None
    output_content: str | None = None
    output_kind: str = "text"
    output_ref: str | None = None
    status: str
    total_tokens: int | None = None
    duration_ms: int
    start_time: datetime


class EventPagePublic(BaseModel):
    rows: list[EventRowPublic]
    total: int
    limit: int
    offset: int


class DailyUsagePublic(BaseModel):
    day: str
    events: int
    tokens: int


class SummaryPublic(BaseModel):
    total_events: int
    success_events: int
    avg_duration_ms: float | None = None
    total_tokens: int
    daily: list[DailyUsagePublic]
    events_by_tool: dict[str, int]


class AiQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AiQueryResponse(BaseModel):
    answer: str


class AiReportRequest(BaseModel):
    tool_id: str = Field(min_length=1)
    start_date: date
    end_date: date
    prompt: str = Field(min_length=1, max_length=12000)


class AiReportResponse(BaseModel):
    html: str
    filename: str
    asset_id: UUID


class ReportAssetPublic(BaseModel):
    asset_id: UUID
    filename: str
    title: str
    tool_id: str
    tool_name: str
    period_start: date
    period_end: date
    created_by: str
    created_at: datetime


class ReportAssetDetailPublic(ReportAssetPublic):
    html: str


def create_app() -> FastAPI:
    application = FastAPI(title="内部工具汇总接入 API")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/portal/tools", response_model=list[ToolCardPublic])
    def portal_tools(
        directory: ToolDirectory = Depends(get_tool_directory),
        reader: UsageEventReader = Depends(get_event_reader),
    ) -> list[ToolCardPublic]:
        counts = reader.summarize().events_by_tool
        return [
            tool_card(tool, usage_count=counts.get(tool.tool_id, 0))
            for tool in directory.list_enabled_tools()
        ]

    @application.get("/analytics/events", response_model=EventPagePublic)
    def analytics_events(
        tool_id: str | None = Query(default=None),
        event_status: Literal["success", "failed", "timeout"] | None = Query(
            default=None, alias="status"
        ),
        since_hours: int | None = Query(default=None, ge=1, le=24 * 365),
        limit: int = Query(default=10, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        reader: UsageEventReader = Depends(get_event_reader),
        directory: ToolDirectory = Depends(get_tool_directory),
        _viewer: TokenClaims = Depends(require_data_viewer),
    ) -> EventPagePublic:
        page = reader.list_events(
            tool_id=tool_id,
            status=event_status,
            since_hours=since_hours,
            limit=limit,
            offset=offset,
        )
        names = {
            tool.tool_id: tool.display_name or tool.name for tool in directory.list_enabled_tools()
        }
        return EventPagePublic(
            rows=[
                EventRowPublic(
                    record_id=row.record_id,
                    tool_id=row.tool_id,
                    tool_name=names.get(row.tool_id, row.tool_id),
                    model=row.model,
                    user_id=row.user_id,
                    user_display_name=row.user_display_name,
                    chapter=row.chapter,
                    input_preview=row.input_preview,
                    output_preview=row.output_preview,
                    output_content=row.output_content,
                    output_kind=row.output_kind,
                    output_ref=row.output_ref,
                    status=row.status,
                    total_tokens=row.total_tokens,
                    duration_ms=row.duration_ms,
                    start_time=row.start_time,
                )
                for row in page.rows
            ],
            total=page.total,
            limit=limit,
            offset=offset,
        )

    @application.get("/analytics/summary", response_model=SummaryPublic)
    def analytics_summary(
        reader: UsageEventReader = Depends(get_event_reader),
        _viewer: TokenClaims = Depends(require_data_viewer),
    ) -> SummaryPublic:
        summary = reader.summarize()
        return SummaryPublic(
            total_events=summary.total_events,
            success_events=summary.success_events,
            avg_duration_ms=summary.avg_duration_ms,
            total_tokens=summary.total_tokens,
            daily=[
                DailyUsagePublic(day=d.day, events=d.events, tokens=d.tokens) for d in summary.daily
            ],
            events_by_tool=summary.events_by_tool,
        )

    @application.post("/ai/query", response_model=AiQueryResponse)
    def ai_query(
        request: AiQueryRequest,
        reader: UsageEventReader = Depends(get_event_reader),
        ask: AskAi | None = Depends(get_ai_answerer),
        _viewer: TokenClaims = Depends(require_data_viewer),
    ) -> AiQueryResponse:
        if ask is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI query is not configured: set APIMART_API_KEY on the server",
            )
        try:
            answer = ask(build_ai_prompt(request.question, reader.summarize()))
        except AiQueryError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        return AiQueryResponse(answer=answer)

    @application.post("/ai/report", response_model=AiReportResponse)
    def ai_report(
        request: AiReportRequest,
        reader: UsageEventReader = Depends(get_event_reader),
        directory: ToolDirectory = Depends(get_tool_directory),
        assets: ReportAssetRepository = Depends(get_report_asset_repository),
        ask: AskAi | None = Depends(get_ai_answerer),
        viewer: TokenClaims = Depends(require_data_viewer),
    ) -> AiReportResponse:
        if request.start_date > request.end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_date must be before or equal to end_date",
            )
        tool = next(
            (item for item in directory.list_enabled_tools() if item.tool_id == request.tool_id),
            None,
        )
        if tool is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool not found")
        if ask is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI report is not configured: set APIMART_API_KEY on the server",
            )
        report_data = reader.tool_report_data(
            tool_id=request.tool_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        try:
            html = ask(build_ai_report_prompt(request.prompt, tool, report_data))
        except AiQueryError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        stripped_html = strip_markdown_fences(html)
        filename = report_filename(tool, request.start_date, request.end_date)
        asset = assets.create_report_asset(
            filename=filename,
            title=report_title(tool, request.start_date, request.end_date),
            tool_id=tool.tool_id,
            tool_name=tool.display_name or tool.name,
            period_start=request.start_date,
            period_end=request.end_date,
            html=stripped_html,
            created_by=viewer.user_id,
        )
        return AiReportResponse(
            html=stripped_html,
            filename=filename,
            asset_id=asset.asset_id,
        )

    @application.get("/assets/reports", response_model=list[ReportAssetPublic])
    def list_report_assets(
        limit: int = Query(default=50, ge=1, le=100),
        assets: ReportAssetRepository = Depends(get_report_asset_repository),
        _viewer: TokenClaims = Depends(require_data_viewer),
    ) -> list[ReportAssetPublic]:
        return [public_report_asset(asset) for asset in assets.list_report_assets(limit=limit)]

    @application.get("/assets/reports/{asset_id}", response_model=ReportAssetDetailPublic)
    def get_report_asset(
        asset_id: UUID,
        assets: ReportAssetRepository = Depends(get_report_asset_repository),
        _viewer: TokenClaims = Depends(require_data_viewer),
    ) -> ReportAssetDetailPublic:
        asset = assets.get_report_asset(asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
        return public_report_asset_detail(asset)

    @application.post(
        "/events",
        response_model=EventIngested,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def ingest_event(
        event: UsageEvent,
        request: Request,
        repository: UsageEventRepository = Depends(get_repository),
        token_claims: TokenClaims | None = Depends(optional_token_claims),
    ) -> EventIngested:
        warn_if_unsupported_schema_version(event)
        normalized = normalize_event(
            event, token_claims=token_claims, source_ip=client_source_ip(request)
        )
        ingested_at = datetime.now(UTC)
        try:
            stored = repository.insert_event(normalized, ingested_at=ingested_at)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="event storage failed",
            ) from exc
        return event_response(stored)

    @application.post("/auth/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
    def create_user(
        request: UserCreateRequest,
        repository: UserAccountRepository = Depends(get_user_repository),
        _admin: TokenClaims = Depends(require_admin),
    ) -> UserPublic:
        account = repository.create_user(
            username=request.username,
            password=request.password,
            user_id=request.user_id,
            team_id=request.team_id,
            role=request.role,
        )
        return public_user(account)

    @application.post(
        "/registry/tools",
        response_model=ToolPublic,
        status_code=status.HTTP_201_CREATED,
    )
    def register_tool(
        request: ToolRegisterRequest,
        repository: ToolRegistryRepository = Depends(get_tool_registry_repository),
        _admin: TokenClaims = Depends(require_admin),
    ) -> ToolPublic:
        # tool_id 由平台统一分配（决策 #9）：注册是管理员动作，与 /auth/users 同一门禁。
        # 格式已由 ToolRegisterRequest 的 pattern 校验；这里只处理重复登记。
        try:
            tool = repository.register_tool(
                tool_id=request.tool_id,
                name=request.name,
                team_id=request.team_id,
                data_level=request.data_level,
                collect_method=request.collect_method,
                model_default=request.model_default,
            )
        except ToolAlreadyExistsError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"tool_id already registered: {request.tool_id}",
            ) from exc
        return public_tool(tool)

    @application.post("/auth/dingtalk", response_model=TokenResponse)
    def dingtalk_login(
        request: DingtalkLoginRequest,
        repository: UserAccountRepository = Depends(get_user_repository),
        auth_client: DingtalkAuthClient = Depends(get_dingtalk_auth_client),
        secret: str = Depends(get_auth_token_secret),
        superadmins: set[str] = Depends(get_superadmin_userids),
    ) -> TokenResponse:
        # 钉钉免登：前台拿到的 code 换 dingtalk userid → 查已同步账号 → 判定身份 → 签发 token。
        try:
            dingtalk_userid = auth_client.get_userinfo_by_code(request.code)
        except Exception as exc:  # 免登 code 无效/过期/钉钉不可达
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="钉钉免登失败，请重试或重新打开页面",
            ) from exc
        account = repository.get_by_dingtalk_userid(dingtalk_userid)
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号未同步，请联系超管在后台同步组织",
            )
        is_superadmin = dingtalk_userid in superadmins
        if is_superadmin and account.role != "admin":
            # 超管隐含 admin 待遇：签发的 token 直接给 admin 角色。
            account = UserAccount(
                user_id=account.user_id,
                username=account.username,
                password_hash=account.password_hash,
                team_id=account.team_id,
                role="admin",
            )
        token, expires_at = issue_token(account, secret=secret, is_superadmin=is_superadmin)
        return TokenResponse(
            access_token=token,
            expires_at=expires_at,
            user=public_user(account).model_copy(update={"is_superadmin": is_superadmin}),
        )

    @application.get("/auth/config", response_model=AuthConfigPublic)
    def auth_config(corp_id: str = Depends(get_dingtalk_corp_id)) -> AuthConfigPublic:
        return AuthConfigPublic(corp_id=corp_id)

    @application.get("/auth/admins", response_model=list[AdminSummaryPublic])
    def list_admins(
        repository: UserAccountRepository = Depends(get_user_repository),
        _su: TokenClaims = Depends(require_superadmin),
    ) -> list[AdminSummaryPublic]:
        return [
            AdminSummaryPublic(
                user_id=a.user_id,
                dingtalk_userid=a.dingtalk_userid,
                display_name=a.display_name,
                role=a.role,
            )
            for a in repository.list_accounts()
        ]

    @application.post("/auth/admins/{user_id}", response_model=UserPublic)
    def set_admin_role(
        user_id: str,
        request: SetRoleRequest,
        repository: UserAccountRepository = Depends(get_user_repository),
        _su: TokenClaims = Depends(require_superadmin),
    ) -> UserPublic:
        account = repository.get_by_user_id(user_id)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
        repository.set_role(user_id, request.role)
        updated = repository.get_by_user_id(user_id)
        assert updated is not None
        return public_user(updated)

    @application.post("/auth/verify", response_model=UserPublic)
    def verify(
        request: VerifyTokenRequest,
        secret: str = Depends(get_auth_token_secret),
    ) -> UserPublic:
        claims = verify_token(request.token, secret=secret)
        if claims is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
        return public_claims(claims)

    @application.get("/auth/me", response_model=UserPublic)
    def me(claims: TokenClaims = Depends(required_token_claims)) -> UserPublic:
        return public_claims(claims)

    return application


def warn_if_unsupported_schema_version(event: UsageEvent) -> None:
    # 不拒收（守「不阻断入库」）：格式合法即收。但若是平台尚未支持解析的版本，
    # 记一条告警，提示运维/分析层这条数据当前还没有对应的解析口径。
    if event.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        logger.warning(
            "accepted event %s with unsupported schema_version %s (supported: %s)",
            event.record_id,
            event.schema_version,
            sorted(SUPPORTED_SCHEMA_VERSIONS),
        )


def normalize_event(
    event: UsageEvent,
    *,
    token_claims: TokenClaims | None = None,
    source_ip: str | None = None,
) -> UsageEvent:
    user_id = token_claims.user_id if token_claims is not None else event.user_id
    team_id = token_claims.team_id if token_claims is not None else event.team_id
    metadata = dict(event.metadata or {})
    if source_ip is not None:
        # 平台服务端盖章的溯源事实（同 ingested_at），覆盖自报值以保证可信。
        metadata["source_ip"] = source_ip
    return event.model_copy(
        update={
            "user_id": user_id or "anonymous",
            "team_id": team_id,
            "metadata": metadata,
            "ingested_at": None,
        }
    )


def client_source_ip(request: Request) -> str | None:
    # 溯源用，非鉴权（决策 #7）：优先取 X-Forwarded-For 第一跳——relay（Phase 2D）转发时
    # 会带回工具真实 IP；否则用直连对端 IP。内网 + 不做写入侧鉴权，XFF 可伪造无妨。
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    if request.client is not None:
        return request.client.host
    return None


def event_response(stored: StoredEvent) -> EventIngested:
    return EventIngested(
        record_id=stored.record_id,
        ingested_at=stored.ingested_at,
        inserted=stored.inserted,
    )


def public_user(account: UserAccount) -> UserPublic:
    return UserPublic(
        user_id=account.user_id,
        username=account.username,
        team_id=account.team_id,
        role=account.role,
    )


def public_tool(tool: ToolRegistration) -> ToolPublic:
    return ToolPublic(
        tool_id=tool.tool_id,
        name=tool.name,
        team_id=tool.team_id,
        data_level=tool.data_level,
        collect_method=tool.collect_method,
        model_default=tool.model_default,
    )


def tool_card(tool: ToolConfig, *, usage_count: int) -> ToolCardPublic:
    return ToolCardPublic(
        tool_id=tool.tool_id,
        display_name=tool.display_name or tool.name,
        category=tool.category,
        description=tool.description,
        icon=tool.icon,
        thumbnail=tool.thumbnail,
        launch_url=tool.launch_url,
        usage_count=usage_count,
    )


def public_report_asset(asset: ReportAsset) -> ReportAssetPublic:
    return ReportAssetPublic(
        asset_id=asset.asset_id,
        filename=asset.filename,
        title=asset.title,
        tool_id=asset.tool_id,
        tool_name=asset.tool_name,
        period_start=asset.period_start,
        period_end=asset.period_end,
        created_by=asset.created_by,
        created_at=asset.created_at,
    )


def public_report_asset_detail(asset: ReportAsset) -> ReportAssetDetailPublic:
    return ReportAssetDetailPublic(
        **public_report_asset(asset).model_dump(),
        html=asset.html,
    )


def build_ai_prompt(question: str, summary: UsageSummary) -> str:
    by_tool = "\n".join(
        f"- {tool_id}: {count} calls" for tool_id, count in sorted(summary.events_by_tool.items())
    )
    daily = "\n".join(f"- {d.day}: {d.events} calls, {d.tokens} tokens" for d in summary.daily)
    avg = "unknown" if summary.avg_duration_ms is None else f"{summary.avg_duration_ms:.0f}ms"
    return (
        "你是公司内部工具平台的数据分析助手。只依据下面的真实平台数据回答，"
        "用中文、简洁、引用具体数字；如果数据不足，请直接说明，不要编造。"
        "派生指标公式尚未定稿，因此只做事实陈述和直观对比。\n\n"
        "[平台数据快照]\n"
        f"- 总调用: {summary.total_events}; 成功: {summary.success_events}\n"
        f"- 平均耗时: {avg}; 累计 token: {summary.total_tokens}\n"
        f"[各工具调用次数]\n{by_tool or '- 暂无'}\n"
        f"[近 14 天逐日]\n{daily or '- 暂无'}\n\n"
        f"[用户问题]\n{question}"
    )


def build_ai_report_prompt(user_prompt: str, tool: ToolConfig, report_data: ToolReportData) -> str:
    current = report_data.current
    previous = report_data.previous
    period_label = (
        f"{current.start_date.isoformat()} 至 {current.end_date.isoformat()},"
        f"对比基期:{previous.start_date.isoformat()} 至 {previous.end_date.isoformat()}"
    )
    return f"""{user_prompt.strip()}

# 本次输入

- 工具名称:{tool.display_name or tool.name}
- 工具简介(可选):{tool.description or "数据缺失"}
- 统计周期:{period_label}
- 数据输入:{format_report_data(report_data)}
- 模板骨架:未配置模板骨架。若无法保证模板原样保留,
  请在 HTML 正文中明确写出“模板骨架缺失,本报告仅为数据草案”,
  不得编造模板样式来源。

# 第〇步:判断输入类型,选择工作模式

- 如果"数据输入"是数据库表结构:不要编写报告。先输出《取数清单》——
  生成本报告所需的每个指标、计算口径、对应 SQL,然后停止,等待我提供查询结果。
- 如果"数据输入"是已查询好的数据:进入第一步,直接产出报告 HTML。

# 第一步:识别工具类型,确定指标体系

根据工具名称、简介和数据字段,将工具归入以下类型之一,分类依据写入附录:

| 工具类型 | 典型特征 | 核心指标 |
|---|---|---|
| 内容生成类 | 写作、摘要、翻译、文案 | 渗透率、采纳率、重新生成率、编辑率、单次成本 |
| 检索问答类 | 知识库问答、搜索 | 渗透率、回答命中率、无结果率、平均耗时 |
| 对话助手类 | 多轮对话、客服辅助 | 会话数、人均轮次、问题解决率、转人工率 |
| 数据处理类 | 批量清洗、自动标注 | 任务量、成功率、人工修正率、单位成本 |

补充规则:
1. 所有类型额外报告:请求成功率、平均耗时、token/成本消耗(数据可得时)。
2. 每个指标给出本期值、环比、同比;基期缺失时如实标注"基期数据缺失",不省略。
3. 无法归类时使用通用指标(使用率、成功率、耗时、成本),并在摘要中注明。
4. 数据中环比变化超过 ±20% 的未覆盖字段,可补充为附加指标并说明理由。

# 第二步:按固定结构产出报告(与模板区块一一对应)

① 报告头:标题(工具名+周期+报告类型)、统计周期、对比基期、数据截止、
   生成时间、AI 生成声明(ai-chip)。
② 核心摘要(3–5 条):每条 = 现象 + 幅度 + 判断;摘要中每个数字必须在正文出现。
③ 关键指标总览:kpi 卡片,每张含指标名、本期值、环比(▲/▼/持平)。
④ 分维度分析(2–4 个 section):优先时间趋势、用户/部门、功能/场景维度。
   每个 section = 编号标题 + 一句话结论(conclusion)+ 图表/表格 + note 口径注释。
⑤ 异常与归因:仅当存在环比 ±15% 以上变化或明显偏离趋势时输出,否则写
   "本期无显著异常"。格式:异常幅度 → 维度下钻 → 原因;数据无法证明的原因
   必须加 tag-infer 标签「推断,待验证」。
⑥ 建议与行动项(≤5 条):行动 + 数据依据(引用具体数字)+ 预期影响 +
   优先级徽章(P0/P1/P2);末尾保留 AI 推断声明。
⑦ 附录:指标口径(含计算式)、数据来源、分类依据、本期局限。

# HTML 输出规范(最高优先级之一)

1. 以"模板骨架"为基础输出完整 HTML。<style> 区、顶部设计令牌区、目录高亮
   脚本、图表 BASE 主题与 renderChart 函数必须原样保留,一个字符都不改。
2. 内容只允许使用模板已定义的组件类:report / toc / report-header / report-meta /
   ai-chip / summary / kpi-grid / kpi / section / conclusion / note /
   data-table(num、alert)/ chart / anomaly / tag-infer / advice /
   badge(p0、p1、p2)/ basis / raw-data / appendix / report-footer。
   禁止编写任何新的 CSS、新 class 或内联 style(图表容器的 height 除外)。
3. 目录规则:
   - .toc 中的 <li> 按报告实际章节生成,顺序与正文一致;
   - 锚点 id 固定命名:sec-summary、sec-kpi、分析章节依次为 sec-a1、sec-a2…、
     sec-anomaly、sec-advice、sec-appendix;
   - 正文每个区块的 id 必须与目录 href 一一对应,不得出现目录有而正文无
     (或相反)的条目;
   - 分析章节的目录文字格式为"序号 · 章节短标题",短标题不超过 10 字。
4. 图表规则:只在脚本区底部"图表数据"处调用 renderChart(容器id, option)
   填入数据(类目、数值、系列名);看趋势用 line,做对比用 bar,异常项可单独
   设 itemStyle.color 为 tok('--up');不引入其他图表库,不修改 BASE;
   图表容器 id 与所在章节对应(如 chart-a1、chart-a2)。
5. 表格规则:一律 class="data-table";数字列加 class="num",千位分隔符,
   同一指标统一小数位;异常行加 class="alert" 并在简评用 ⚠ 标记;
   涨跌用 ▲/▼ 符号 + 数值;超过 15 行的明细数据放入
   <details class="raw-data"> 折叠区,汇总表保留在折叠区外。
6. 除 HTML 文件本身外不输出任何其他内容(不要解释、不要 Markdown 代码围栏)。

# 数据使用规则(最高优先级,违反任何一条即为错误输出)

1. 报告中出现的每一个数字,必须直接来自输入数据,或由输入数据明确计算得出;
   计算得出的数字在附录口径中给出计算式。
2. 禁止编造、估计、回忆任何数字。数据缺失时如实写"数据缺失",并列入附录局限。
3. 环比/同比仅在基期数据存在时计算,否则标注"基期数据缺失"。
4. 归因只能基于输入数据中可见的维度;数据之外的解释一律加「推断,待验证」标签。
5. 不得引用本输入之外的行业数据、基准值或"通常情况"。
6. 百分比指标写明分子分母;分母为零或样本量 < 30 时标注
   "样本量不足,结论仅供参考"。
"""


def format_report_data(data: ToolReportData) -> str:
    def period_block(label: str, period: ReportPeriod) -> str:
        rows = [
            f"## {label}",
            f"- 周期: {period.start_date.isoformat()} 至 {period.end_date.isoformat()}",
            f"- 总请求数: {period.total_events}",
            f"- 成功请求数: {period.success_events}",
            "- 平均耗时毫秒: "
            + (
                str(period.avg_duration_ms)
                if period.avg_duration_ms is not None
                else "数据缺失"
            ),
            f"- 总 token: {period.total_tokens}",
            "- 按日: "
            + "; ".join(
                f"{item.day}: 请求 {item.events}, token {item.tokens}"
                for item in period.daily
            ),
            "- 按状态: " + format_breakdowns(period.status),
            "- 按用户: " + format_breakdowns(period.users),
            "- 按功能/章节: " + format_breakdowns(period.chapters),
        ]
        return "\n".join(rows)

    return "\n\n".join(
        [
            "以下为已查询好的汇总数据,不是数据库表结构。",
            f"工具 ID: {data.tool_id}",
            period_block("本期", data.current),
            period_block("对比基期", data.previous),
        ]
    )


def format_breakdowns(items: list[ReportMetricBreakdown]) -> str:
    if not items:
        return "数据缺失"
    return "; ".join(
        (
            f"{item.name}: 请求 {item.events}, token {item.tokens}, "
            f"平均耗时 {item.avg_duration_ms if item.avg_duration_ms is not None else '数据缺失'}"
        )
        for item in items
    )


def strip_markdown_fences(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def report_filename(tool: ToolConfig, start_date: date, end_date: date) -> str:
    safe_tool = "".join(
        char if char.isalnum() or char in ("-", "_") else "-"
        for char in (tool.display_name or tool.name or tool.tool_id)
    ).strip("-")
    return (
        f"{safe_tool or tool.tool_id}-"
        f"{start_date.isoformat()}-{end_date.isoformat()}-AI报告.html"
    )


def report_title(tool: ToolConfig, start_date: date, end_date: date) -> str:
    return (
        f"{tool.display_name or tool.name} "
        f"{start_date.isoformat()} 至 {end_date.isoformat()} 报告"
    )


def public_claims(claims: TokenClaims) -> UserPublic:
    return UserPublic(
        user_id=claims.user_id,
        username=claims.username,
        team_id=claims.team_id,
        role=claims.role,
    )


def cors_allow_origins() -> list[str]:
    # 鉴权走 Authorization 头（无 cookie），通配不会放大 CSRF 面；正式部署仍应在
    # PORTAL_CORS_ORIGINS 填门户来源（逗号分隔），见 .env.example。
    raw = os.environ.get("PORTAL_CORS_ORIGINS", "*")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_auth_token_secret() -> str:
    value = os.environ.get("AUTH_TOKEN_SECRET")
    if value is None or not value.strip():
        raise RuntimeError("AUTH_TOKEN_SECRET is required")
    return value


def optional_token_claims(
    authorization: str | None = Header(default=None),
    secret: str = Depends(get_auth_token_secret),
) -> TokenClaims | None:
    token = bearer_token(authorization)
    if token is None:
        return None
    claims = verify_token(token, secret=secret)
    if claims is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    return claims


def required_token_claims(
    claims: TokenClaims | None = Depends(optional_token_claims),
) -> TokenClaims:
    if claims is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    return claims


def require_admin(claims: TokenClaims = Depends(required_token_claims)) -> TokenClaims:
    # 创建账号是管理员动作：内网威胁模型下不做写入侧鉴权（事件上报），但账号体系是
    # 读取侧权限的挂靠点，必须挡住「任何人给自己开 admin」。
    if claims.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin role required",
        )
    return claims


def require_data_viewer(claims: TokenClaims = Depends(required_token_claims)) -> TokenClaims:
    # 数据端（统计/明细/AI 查询）仅 admin 或超管可见（决策 #44 更正：免登 + 角色门禁）。
    if claims.role != "admin" and not claims.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权查看数据，请联系超管开通",
        )
    return claims


def require_superadmin(claims: TokenClaims = Depends(required_token_claims)) -> TokenClaims:
    # 增减 admin 只认超管（BOOTSTRAP_ADMIN_DINGTALK_USERID 配置认定，UI 不可改）。
    if not claims.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅超管可操作",
        )
    return claims


class DingtalkAuthClient(Protocol):
    """免登换身份的最小能力（抽象，便于测试覆盖）。"""

    def get_userinfo_by_code(self, code: str) -> str: ...


@lru_cache(maxsize=1)
def get_superadmin_userids() -> set[str]:
    return parse_superadmin_userids(os.environ.get("BOOTSTRAP_ADMIN_DINGTALK_USERID"))


@lru_cache(maxsize=1)
def get_dingtalk_corp_id() -> str:
    return os.environ.get("DINGTALK_CORP_ID", "")


@lru_cache(maxsize=1)
def get_dingtalk_auth_client() -> DingtalkAuthClient:
    client_id = os.environ.get("DINGTALK_CLIENT_ID")
    client_secret = os.environ.get("DINGTALK_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("DINGTALK_CLIENT_ID / DINGTALK_CLIENT_SECRET are required for 免登")
    return HttpxDingtalkClient(client_id=client_id, client_secret=client_secret)


@lru_cache(maxsize=1)
def get_database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if value is None or not value.strip():
        raise RuntimeError("DATABASE_URL is required")
    return value


@lru_cache(maxsize=1)
def get_repository() -> UsageEventRepository:
    return PostgresUsageEventRepository(get_database_url())


@lru_cache(maxsize=1)
def get_user_repository() -> UserAccountRepository:
    return PostgresUserAccountRepository(get_database_url())


@lru_cache(maxsize=1)
def get_tool_registry_repository() -> ToolRegistryRepository:
    return PostgresToolRegistryRepository(get_database_url())


@lru_cache(maxsize=1)
def get_event_reader() -> UsageEventReader:
    return PostgresUsageEventReader(get_database_url())


@lru_cache(maxsize=1)
def get_tool_directory() -> ToolDirectory:
    return PostgresToolDirectory(get_database_url())


@lru_cache(maxsize=1)
def get_report_asset_repository() -> ReportAssetRepository:
    return PostgresReportAssetRepository(get_database_url())


AskAi = Callable[[str], str]


def get_ai_answerer() -> AskAi | None:
    api_key = os.environ.get("APIMART_API_KEY")
    if api_key is None or not api_key.strip():
        return None
    if api_key.strip() in {"填你的APIMart密钥", "your-apimart-api-key"}:
        return None
    client = ApimartGeminiClient(
        api_key=api_key,
        base_url=os.environ.get("APIMART_BASE_URL", DEFAULT_BASE_URL),
        model=os.environ.get("APIMART_MODEL", DEFAULT_MODEL),
    )
    return client.ask


app = create_app()
