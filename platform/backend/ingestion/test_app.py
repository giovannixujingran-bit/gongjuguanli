from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from backend.auth.accounts import AccountSummary, Role, UserAccount, UserAccountRepository
from backend.auth.passwords import hash_password
from backend.ingestion.ai_query import AiQueryError
from backend.ingestion.app import (
    create_app,
    get_ai_answerer,
    get_auth_token_secret,
    get_dingtalk_auth_client,
    get_event_reader,
    get_repository,
    get_superadmin_userids,
    get_tool_directory,
    get_tool_registry_repository,
    get_user_repository,
)
from backend.storage.events import DailyUsage, EventPage, EventRow, StoredEvent, UsageSummary
from backend.storage.registry import (
    CollectMethod,
    DataLevel,
    ToolAlreadyExistsError,
    ToolConfig,
    ToolRegistration,
    ToolRegistryRepository,
)
from shared.contracts.event_model import UsageEvent

SAMPLE_RECORD_ID = "018f6b43-2e69-7a2b-9b34-111111111111"


@dataclass
class MemoryUsageEventRepository:
    events: dict[UUID, tuple[UsageEvent, datetime]] = field(default_factory=dict)

    def insert_event(self, event: UsageEvent, *, ingested_at: datetime) -> StoredEvent:
        existing = self.events.get(event.record_id)
        if existing is not None:
            return StoredEvent(
                record_id=event.record_id,
                ingested_at=existing[1],
                inserted=False,
            )

        self.events[event.record_id] = (event, ingested_at)
        return StoredEvent(record_id=event.record_id, ingested_at=ingested_at, inserted=True)


@dataclass
class MemoryUserAccountRepository:
    users_by_username: dict[str, UserAccount] = field(default_factory=dict)
    users_by_id: dict[str, UserAccount] = field(default_factory=dict)
    users_by_dingtalk: dict[str, UserAccount] = field(default_factory=dict)
    display_names: dict[str, str] = field(default_factory=dict)
    dingtalk_ids: dict[str, str] = field(default_factory=dict)

    def create_user(
        self,
        *,
        username: str,
        password: str,
        user_id: str | None = None,
        team_id: str | None = None,
        role: Role = "user",
        dingtalk_userid: str | None = None,
        display_name: str | None = None,
    ) -> UserAccount:
        account = UserAccount(
            user_id=user_id or f"user-{len(self.users_by_id) + 1}",
            username=username,
            password_hash=hash_password(password) if password else None,
            team_id=team_id,
            role=role,
        )
        self.users_by_username[username] = account
        self.users_by_id[account.user_id] = account
        if dingtalk_userid is not None:
            self.users_by_dingtalk[dingtalk_userid] = account
            self.dingtalk_ids[account.user_id] = dingtalk_userid
        if display_name is not None:
            self.display_names[account.user_id] = display_name
        return account

    def get_by_username(self, username: str) -> UserAccount | None:
        return self.users_by_username.get(username)

    def get_by_user_id(self, user_id: str) -> UserAccount | None:
        return self.users_by_id.get(user_id)

    def get_by_dingtalk_userid(self, dingtalk_userid: str) -> UserAccount | None:
        return self.users_by_dingtalk.get(dingtalk_userid)

    def list_accounts(self) -> list[AccountSummary]:
        return [
            AccountSummary(
                user_id=a.user_id,
                dingtalk_userid=self.dingtalk_ids.get(a.user_id),
                display_name=self.display_names.get(a.user_id),
                role=a.role,
            )
            for a in self.users_by_id.values()
        ]

    def set_role(self, user_id: str, role: Role) -> None:
        old = self.users_by_id[user_id]
        updated = UserAccount(
            user_id=old.user_id,
            username=old.username,
            password_hash=old.password_hash,
            team_id=old.team_id,
            role=role,
        )
        self.users_by_id[user_id] = updated
        self.users_by_username[old.username] = updated
        dd = self.dingtalk_ids.get(user_id)
        if dd is not None:
            self.users_by_dingtalk[dd] = updated


@dataclass
class FakeDingtalkAuthClient:
    """免登假实现：把 code 映射成 dingtalk userid（测试铸 token 用）。"""

    code_to_userid: dict[str, str] = field(default_factory=dict)

    def get_userinfo_by_code(self, code: str) -> str:
        if code not in self.code_to_userid:
            raise KeyError(code)
        return self.code_to_userid[code]


@dataclass
class MemoryToolRegistryRepository:
    tools: dict[str, ToolRegistration] = field(default_factory=dict)

    def register_tool(
        self,
        *,
        tool_id: str,
        name: str,
        team_id: str | None = None,
        data_level: DataLevel = "minimal",
        collect_method: CollectMethod = "report",
        model_default: str | None = None,
    ) -> ToolRegistration:
        if tool_id in self.tools:
            raise ToolAlreadyExistsError(tool_id)
        tool = ToolRegistration(
            tool_id=tool_id,
            name=name,
            team_id=team_id,
            data_level=data_level,
            collect_method=collect_method,
            model_default=model_default,
        )
        self.tools[tool_id] = tool
        return tool

    def get_tool(self, tool_id: str) -> ToolRegistration | None:
        return self.tools.get(tool_id)


SAMPLE_SUMMARY = UsageSummary(
    total_events=8,
    success_events=6,
    avg_duration_ms=2100.0,
    total_tokens=12345,
    daily=[DailyUsage(day="2026-06-10", events=3, tokens=4000)],
    events_by_tool={"aird-report": 8},
)


SAMPLE_TOOL = ToolConfig(
    tool_id="aird-report",
    name="AI报告",
    team_id="aird",
    data_level="partial",
    collect_method="report",
    category="趋势资产",
    display_name="AI报告生成平台",
    description='AI辅助生成趋势报告，目前稳定支持"风格/主题/单品"企划',
    launch_url="https://192.168.40.105:5173/",
)


@dataclass
class MemoryUsageEventReader:
    page: EventPage
    summary: UsageSummary
    seen_filters: dict[str, object] = field(default_factory=dict)

    def list_events(
        self,
        *,
        tool_id: str | None = None,
        status: str | None = None,
        since_hours: int | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> EventPage:
        self.seen_filters = {
            "tool_id": tool_id,
            "status": status,
            "since_hours": since_hours,
            "limit": limit,
            "offset": offset,
        }
        return self.page

    def summarize(self) -> UsageSummary:
        return self.summary


@dataclass
class MemoryToolDirectory:
    tools: list[ToolConfig] = field(default_factory=lambda: [SAMPLE_TOOL])

    def list_enabled_tools(self) -> list[ToolConfig]:
        return self.tools


def sample_event_row() -> EventRow:
    return EventRow(
        record_id=UUID(SAMPLE_RECORD_ID),
        tool_id="aird-report",
        model="gemini-3.5-flash",
        user_id="user-001",
        user_display_name="张三",
        chapter="cover",
        input_preview="生成风格企划",
        output_preview="报告生成成功",
        output_content="报告生成成功，已输出封面章节。",
        output_kind="text",
        output_ref=None,
        status="success",
        total_tokens=1240,
        duration_ms=1200,
        start_time=datetime(2026, 6, 10, 8, 0, tzinfo=UTC),
    )


def test_ingest_event_accepts_simulated_payload_and_defaults_anonymous_user() -> None:
    repository = MemoryUsageEventRepository()
    client = client_with_repository(repository)

    response = client.post("/events", json=sample_payload(user_id=None))

    assert response.status_code == 202
    assert response.json()["record_id"] == SAMPLE_RECORD_ID
    assert response.json()["inserted"] is True
    stored_event = repository.events[UUID(SAMPLE_RECORD_ID)][0]
    assert stored_event.user_id == "anonymous"
    # 平台服务端盖来源 IP（TestClient 直连对端默认为 "testclient"）
    assert stored_event.metadata == {"source_ip": "testclient"}
    assert stored_event.ingested_at is None


def test_ingest_event_stamps_source_ip_from_forwarded_header() -> None:
    repository = MemoryUsageEventRepository()
    client = client_with_repository(repository)

    response = client.post(
        "/events",
        json=sample_payload(user_id=None),
        headers={"X-Forwarded-For": "10.1.2.3, 192.168.0.1"},
    )

    assert response.status_code == 202
    stored_event = repository.events[UUID(SAMPLE_RECORD_ID)][0]
    # X-Forwarded-For 第一跳优先（relay 转发回的工具真实 IP）
    assert stored_event.metadata is not None
    assert stored_event.metadata["source_ip"] == "10.1.2.3"


def test_ingest_event_is_idempotent_by_record_id() -> None:
    repository = MemoryUsageEventRepository()
    client = client_with_repository(repository)

    first = client.post("/events", json=sample_payload())
    second = client.post("/events", json=sample_payload())

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["inserted"] is True
    assert second.json()["inserted"] is False
    assert len(repository.events) == 1


def test_ingest_event_rejects_missing_required_field() -> None:
    repository = MemoryUsageEventRepository()
    client = client_with_repository(repository)
    payload = sample_payload()
    del payload["tool_id"]

    response = client.post("/events", json=payload)

    assert response.status_code == 422
    assert repository.events == {}


def test_portal_tools_returns_cards_with_real_usage_counts() -> None:
    client, _, _ = read_client()

    # 门户卡片不含敏感内容，首页无登录态，保持公开。
    response = client.get("/portal/tools")

    assert response.status_code == 200
    [card] = response.json()
    assert card["tool_id"] == "aird-report"
    assert card["display_name"] == "AI报告生成平台"
    assert card["category"] == "趋势资产"
    assert card["launch_url"] == "https://192.168.40.105:5173/"
    assert card["usage_count"] == 8


def test_read_side_requires_login() -> None:
    # 决策 #44：分析明细/聚合与 AI 查询必须带登录态 token（敏感细则仍待定，先挡匿名）。
    client, _, _ = read_client()

    assert client.get("/analytics/events").status_code == 401
    assert client.get("/analytics/summary").status_code == 401
    assert client.post("/ai/query", json={"question": "hi"}).status_code == 401


def test_analytics_events_resolves_tool_name_and_passes_filters() -> None:
    client, reader, auth = read_client()

    response = client.get(
        "/analytics/events",
        headers=auth,
        params={"tool_id": "aird-report", "status": "success", "since_hours": 24, "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["rows"][0]["tool_name"] == "AI报告生成平台"
    assert body["rows"][0]["user_display_name"] == "张三"
    assert body["rows"][0]["chapter"] == "cover"
    assert body["rows"][0]["output_content"] == "报告生成成功，已输出封面章节。"
    assert body["rows"][0]["output_kind"] == "text"
    assert body["rows"][0]["total_tokens"] == 1240
    assert reader.seen_filters == {
        "tool_id": "aird-report",
        "status": "success",
        "since_hours": 24,
        "limit": 5,
        "offset": 0,
    }


def test_analytics_summary_returns_raw_aggregates() -> None:
    client, _, auth = read_client()

    response = client.get("/analytics/summary", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] == 8
    assert body["success_events"] == 6
    assert body["total_tokens"] == 12345
    assert body["daily"] == [{"day": "2026-06-10", "events": 3, "tokens": 4000}]
    assert body["events_by_tool"] == {"aird-report": 8}


def test_ai_query_returns_503_when_key_not_configured() -> None:
    client, _, auth = read_client(ai_answerer=None)

    response = client.post("/ai/query", headers=auth, json={"question": "上周用量怎么样？"})

    assert response.status_code == 503
    assert "APIMART_API_KEY" in response.json()["detail"]


def test_ai_query_feeds_real_summary_into_prompt() -> None:
    prompts: list[str] = []

    def fake_ask(prompt: str) -> str:
        prompts.append(prompt)
        return "共 8 次调用。"

    client, _, auth = read_client(ai_answerer=fake_ask)

    response = client.post("/ai/query", headers=auth, json={"question": "总共调用了多少次？"})

    assert response.status_code == 200
    assert response.json()["answer"] == "共 8 次调用。"
    [prompt] = prompts
    assert "总调用: 8" in prompt
    assert "aird-report: 8 calls" in prompt
    assert "总共调用了多少次？" in prompt


def test_ai_query_maps_upstream_failure_to_502() -> None:
    def failing_ask(prompt: str) -> str:
        raise AiQueryError("boom")

    client, _, auth = read_client(ai_answerer=failing_ask)

    response = client.post("/ai/query", headers=auth, json={"question": "你好"})

    assert response.status_code == 502


def test_dingtalk_login_then_me() -> None:
    user_repository = MemoryUserAccountRepository()
    user_repository.create_user(
        username="dd-alice",
        password="",
        user_id="user-001",
        team_id="team-a",
        dingtalk_userid="dd-alice",
        display_name="爱丽丝",
    )
    client = client_with_repositories(
        MemoryUsageEventRepository(),
        user_repository=user_repository,
        auth_codes={"alice-code": "dd-alice"},
    )

    token = mint_token(client, "alice-code")
    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me_response.status_code == 200
    assert me_response.json()["user_id"] == "user-001"


def test_create_user_requires_admin() -> None:
    user_repository = MemoryUserAccountRepository()
    user_repository.create_user(
        username="dd-bob",
        password="",
        user_id="user-002",
        role="user",
        dingtalk_userid="dd-bob",
    )
    client = client_with_repositories(
        MemoryUsageEventRepository(),
        user_repository=user_repository,
        auth_codes={"bob-code": "dd-bob"},
    )
    payload = {"username": "mallory", "password": "secret", "role": "admin"}

    no_token = client.post("/auth/users", json=payload)
    user_token = mint_token(client, "bob-code")
    non_admin = client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {user_token}"},
        json=payload,
    )

    assert no_token.status_code == 401
    assert non_admin.status_code == 403
    assert user_repository.get_by_username("mallory") is None


def test_ingest_event_uses_verified_token_identity_over_payload_user_id() -> None:
    event_repository = MemoryUsageEventRepository()
    user_repository = MemoryUserAccountRepository()
    user_repository.create_user(
        username="dd-alice",
        password="",
        user_id="user-001",
        team_id="team-a",
        dingtalk_userid="dd-alice",
    )
    client = client_with_repositories(
        event_repository,
        user_repository=user_repository,
        auth_codes={"alice-code": "dd-alice"},
    )
    token = mint_token(client, "alice-code")
    payload = sample_payload(user_id="spoofed-user")

    response = client.post("/events", json=payload, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 202
    stored_event = event_repository.events[UUID(SAMPLE_RECORD_ID)][0]
    assert stored_event.user_id == "user-001"
    assert stored_event.team_id == "team-a"


def test_admin_registers_tool_and_gets_assigned_id() -> None:
    registry = MemoryToolRegistryRepository()
    client, admin_token = admin_client(tool_registry_repository=registry)

    response = client.post(
        "/registry/tools",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"tool_id": "infra-log-exporter", "name": "日志导出器", "team_id": "infra"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tool_id"] == "infra-log-exporter"
    assert body["team_id"] == "infra"
    # 未给的接入字段走默认（决策 #9 注册表底表默认）
    assert body["data_level"] == "minimal"
    assert body["collect_method"] == "report"
    assert registry.get_tool("infra-log-exporter") is not None


def test_register_tool_requires_admin() -> None:
    registry = MemoryToolRegistryRepository()
    user_repository = MemoryUserAccountRepository()
    user_repository.create_user(
        username="dd-bob",
        password="",
        user_id="user-002",
        role="user",
        dingtalk_userid="dd-bob",
    )
    client = client_with_repositories(
        MemoryUsageEventRepository(),
        user_repository=user_repository,
        tool_registry_repository=registry,
        auth_codes={"bob-code": "dd-bob"},
    )
    payload = {"tool_id": "infra-log-exporter", "name": "日志导出器"}

    no_token = client.post("/registry/tools", json=payload)
    user_token = mint_token(client, "bob-code")
    non_admin = client.post(
        "/registry/tools",
        headers={"Authorization": f"Bearer {user_token}"},
        json=payload,
    )

    assert no_token.status_code == 401
    assert non_admin.status_code == 403
    assert registry.get_tool("infra-log-exporter") is None


def test_register_tool_rejects_duplicate_tool_id() -> None:
    registry = MemoryToolRegistryRepository()
    client, admin_token = admin_client(tool_registry_repository=registry)
    payload = {"tool_id": "infra-log-exporter", "name": "日志导出器"}
    headers = {"Authorization": f"Bearer {admin_token}"}

    first = client.post("/registry/tools", headers=headers, json=payload)
    second = client.post("/registry/tools", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert len(registry.tools) == 1


def test_register_tool_rejects_invalid_tool_id_format() -> None:
    registry = MemoryToolRegistryRepository()
    client, admin_token = admin_client(tool_registry_repository=registry)
    headers = {"Authorization": f"Bearer {admin_token}"}
    # 违反 `<team>-<tool>` kebab：大写 / 单段 / 下划线 / 双连字符 / 前后缀连字符
    invalid_ids = [
        "InfraTool",
        "logexporter",
        "infra_log",
        "infra--log",
        "-infra-log",
        "infra-log-",
    ]

    for tool_id in invalid_ids:
        response = client.post(
            "/registry/tools",
            headers=headers,
            json={"tool_id": tool_id, "name": "x"},
        )
        assert response.status_code == 422, tool_id

    assert registry.tools == {}


def client_with_repository(repository: MemoryUsageEventRepository) -> TestClient:
    return client_with_repositories(repository)


def read_client(
    *,
    summary: UsageSummary = SAMPLE_SUMMARY,
    ai_answerer: Callable[[str], str] | None = None,
) -> tuple[TestClient, MemoryUsageEventReader, dict[str, str]]:
    """Client + reader + 一个普通登录用户的 Authorization 头（读取侧门禁用）。"""
    reader = MemoryUsageEventReader(
        page=EventPage(rows=[sample_event_row()], total=1),
        summary=summary,
    )
    user_repository = MemoryUserAccountRepository()
    # 数据端现仅 admin/超管可见（决策 #44 更正）：数据读取用例的账号给 admin。
    user_repository.create_user(
        username="viewer",
        password="",
        user_id="user-009",
        role="admin",
        dingtalk_userid="dd-viewer",
    )
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: MemoryUsageEventRepository()
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_auth_token_secret] = lambda: "test-secret"
    app.dependency_overrides[get_event_reader] = lambda: reader
    app.dependency_overrides[get_tool_directory] = lambda: MemoryToolDirectory()
    app.dependency_overrides[get_ai_answerer] = lambda: ai_answerer
    app.dependency_overrides[get_dingtalk_auth_client] = lambda: FakeDingtalkAuthClient(
        {"viewer-code": "dd-viewer"}
    )
    app.dependency_overrides[get_superadmin_userids] = lambda: set()
    client = TestClient(app)
    token = client.post("/auth/dingtalk", json={"code": "viewer-code"}).json()["access_token"]
    return client, reader, {"Authorization": f"Bearer {token}"}


def client_with_repositories(
    repository: MemoryUsageEventRepository,
    *,
    user_repository: UserAccountRepository | None = None,
    tool_registry_repository: ToolRegistryRepository | None = None,
    auth_codes: dict[str, str] | None = None,
    superadmins: set[str] | None = None,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    if user_repository is not None:
        app.dependency_overrides[get_user_repository] = lambda: user_repository
    if tool_registry_repository is not None:
        app.dependency_overrides[get_tool_registry_repository] = lambda: tool_registry_repository
    app.dependency_overrides[get_auth_token_secret] = lambda: "test-secret"
    app.dependency_overrides[get_dingtalk_auth_client] = lambda: FakeDingtalkAuthClient(
        auth_codes or {}
    )
    app.dependency_overrides[get_superadmin_userids] = lambda: superadmins or set()
    return TestClient(app)


def mint_token(client: TestClient, code: str) -> str:
    token = client.post("/auth/dingtalk", json={"code": code}).json()["access_token"]
    assert isinstance(token, str)
    return token


def admin_client(
    *,
    tool_registry_repository: ToolRegistryRepository | None = None,
) -> tuple[TestClient, str]:
    """Build a client plus an admin bearer token (钉钉免登铸造)。"""
    user_repository = MemoryUserAccountRepository()
    user_repository.create_user(
        username="dd-root",
        password="",
        user_id="admin-001",
        role="admin",
        dingtalk_userid="dd-root",
        display_name="管理员",
    )
    client = client_with_repositories(
        MemoryUsageEventRepository(),
        user_repository=user_repository,
        tool_registry_repository=tool_registry_repository,
        auth_codes={"root-code": "dd-root"},
    )
    return client, mint_token(client, "root-code")


def sample_payload(*, user_id: str | None = "user-001") -> dict[str, object]:
    payload: dict[str, object] = {
        "record_id": SAMPLE_RECORD_ID,
        "schema_version": "v0.2",
        "tool_id": "mock-tool",
        "conversation_id": "mock-conversation",
        "start_time": "2026-06-03T08:00:00Z",
        "end_time": "2026-06-03T08:00:02Z",
        "duration_ms": 2000,
        "status": "success",
        "model": "mock-model",
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
        "cost": 0.001,
        "cost_source": "source",
        "team_id": "team-a",
        "result_quality": 0.95,
        "adopted": True,
        "input_content": "mock input",
        "output_content": "mock output",
    }
    if user_id is not None:
        payload["user_id"] = user_id
    return payload
