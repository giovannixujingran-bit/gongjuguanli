from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from fastapi.testclient import TestClient

from backend.auth.accounts import Role, UserAccount, UserAccountRepository
from backend.auth.passwords import hash_password
from backend.ingestion.app import (
    create_app,
    get_auth_token_secret,
    get_repository,
    get_tool_registry_repository,
    get_user_repository,
)
from backend.storage.events import StoredEvent
from backend.storage.registry import (
    CollectMethod,
    DataLevel,
    ToolAlreadyExistsError,
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

    def create_user(
        self,
        *,
        username: str,
        password: str,
        user_id: str | None = None,
        team_id: str | None = None,
        role: Role = "user",
    ) -> UserAccount:
        account = UserAccount(
            user_id=user_id or f"user-{len(self.users_by_id) + 1}",
            username=username,
            password_hash=hash_password(password),
            team_id=team_id,
            role=role,
        )
        self.users_by_username[username] = account
        self.users_by_id[account.user_id] = account
        return account

    def get_by_username(self, username: str) -> UserAccount | None:
        return self.users_by_username.get(username)

    def get_by_user_id(self, user_id: str) -> UserAccount | None:
        return self.users_by_id.get(user_id)


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


def test_ingest_event_accepts_simulated_payload_and_defaults_anonymous_user() -> None:
    repository = MemoryUsageEventRepository()
    client = client_with_repository(repository)

    response = client.post("/events", json=sample_payload(user_id=None))

    assert response.status_code == 202
    assert response.json()["record_id"] == SAMPLE_RECORD_ID
    assert response.json()["inserted"] is True
    stored_event = repository.events[UUID(SAMPLE_RECORD_ID)][0]
    assert stored_event.user_id == "anonymous"
    assert stored_event.metadata == {}
    assert stored_event.ingested_at is None


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


def test_admin_creates_user_then_login_and_me() -> None:
    user_repository = MemoryUserAccountRepository()
    user_repository.create_user(
        username="root",
        password="root-secret",
        user_id="admin-001",
        role="admin",
    )
    client = client_with_repositories(
        MemoryUsageEventRepository(),
        user_repository=user_repository,
    )
    admin_token = client.post(
        "/auth/login",
        json={"username": "root", "password": "root-secret"},
    ).json()["access_token"]

    create_response = client.post(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "alice",
            "password": "secret",
            "user_id": "user-001",
            "team_id": "team-a",
        },
    )
    login_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret"},
    )

    assert create_response.status_code == 201
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["user_id"] == "user-001"


def test_create_user_requires_admin() -> None:
    user_repository = MemoryUserAccountRepository()
    user_repository.create_user(
        username="bob",
        password="secret",
        user_id="user-002",
        role="user",
    )
    client = client_with_repositories(
        MemoryUsageEventRepository(),
        user_repository=user_repository,
    )
    payload = {"username": "mallory", "password": "secret", "role": "admin"}

    no_token = client.post("/auth/users", json=payload)
    user_token = client.post(
        "/auth/login",
        json={"username": "bob", "password": "secret"},
    ).json()["access_token"]
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
        username="alice",
        password="secret",
        user_id="user-001",
        team_id="team-a",
    )
    client = client_with_repositories(event_repository, user_repository=user_repository)
    token = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret"},
    ).json()["access_token"]
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
        username="bob",
        password="secret",
        user_id="user-002",
        role="user",
    )
    client = client_with_repositories(
        MemoryUsageEventRepository(),
        user_repository=user_repository,
        tool_registry_repository=registry,
    )
    payload = {"tool_id": "infra-log-exporter", "name": "日志导出器"}

    no_token = client.post("/registry/tools", json=payload)
    user_token = client.post(
        "/auth/login",
        json={"username": "bob", "password": "secret"},
    ).json()["access_token"]
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


def client_with_repositories(
    repository: MemoryUsageEventRepository,
    *,
    user_repository: UserAccountRepository | None = None,
    tool_registry_repository: ToolRegistryRepository | None = None,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    if user_repository is not None:
        app.dependency_overrides[get_user_repository] = lambda: user_repository
    if tool_registry_repository is not None:
        app.dependency_overrides[get_tool_registry_repository] = lambda: tool_registry_repository
    app.dependency_overrides[get_auth_token_secret] = lambda: "test-secret"
    return TestClient(app)


def admin_client(
    *,
    tool_registry_repository: ToolRegistryRepository | None = None,
) -> tuple[TestClient, str]:
    """Build a client plus an admin bearer token (root/root-secret)."""
    user_repository = MemoryUserAccountRepository()
    user_repository.create_user(
        username="root",
        password="root-secret",
        user_id="admin-001",
        role="admin",
    )
    client = client_with_repositories(
        MemoryUsageEventRepository(),
        user_repository=user_repository,
        tool_registry_repository=tool_registry_repository,
    )
    token = client.post(
        "/auth/login",
        json={"username": "root", "password": "root-secret"},
    ).json()["access_token"]
    return client, token


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
