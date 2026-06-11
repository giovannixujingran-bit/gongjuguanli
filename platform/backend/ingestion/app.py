from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.auth.accounts import (
    PostgresUserAccountRepository,
    Role,
    UserAccount,
    UserAccountRepository,
    authenticate,
)
from backend.auth.tokens import TokenClaims, bearer_token, issue_token, verify_token
from backend.storage.events import PostgresUsageEventRepository, StoredEvent, UsageEventRepository
from backend.storage.registry import (
    TOOL_ID_REGEX,
    CollectMethod,
    DataLevel,
    PostgresToolRegistryRepository,
    ToolAlreadyExistsError,
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


class LoginRequest(BaseModel):
    username: str
    password: str


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


def create_app() -> FastAPI:
    application = FastAPI(title="内部工具汇总接入 API")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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

    @application.post("/auth/login", response_model=TokenResponse)
    def login(
        request: LoginRequest,
        repository: UserAccountRepository = Depends(get_user_repository),
        secret: str = Depends(get_auth_token_secret),
    ) -> TokenResponse:
        account = authenticate(repository, username=request.username, password=request.password)
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid username or password",
            )
        token, expires_at = issue_token(account, secret=secret)
        return TokenResponse(
            access_token=token,
            expires_at=expires_at,
            user=public_user(account),
        )

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


def public_claims(claims: TokenClaims) -> UserPublic:
    return UserPublic(
        user_id=claims.user_id,
        username=claims.username,
        team_id=claims.team_id,
        role=claims.role,
    )


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
    # 读取侧权限的挂靠点，必须挡住「任何人给自己开 admin」。首个 admin 由 tools/seed_admin.py
    # 用 DB 凭据离线引导，不经此端点。
    if claims.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin role required",
        )
    return claims


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


app = create_app()
