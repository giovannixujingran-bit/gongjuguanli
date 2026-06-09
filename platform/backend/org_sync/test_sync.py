from __future__ import annotations

from backend.org_sync.client import DingtalkDept, DingtalkUser
from backend.org_sync.sync import collect_departments, sync_organization


class FakeClient:
    """内存版钉钉客户端，喂固定的部门树 + 成员，供纯逻辑单测。"""

    def __init__(
        self,
        children: dict[int, list[DingtalkDept]],
        dept_users: dict[int, list[str]],
        users: dict[str, DingtalkUser],
    ) -> None:
        self._children = children
        self._dept_users = dept_users
        self._users = users

    def list_sub_departments(self, parent_id: int) -> list[DingtalkDept]:
        return list(self._children.get(parent_id, []))

    def list_department_user_ids(self, dept_id: int) -> list[str]:
        return list(self._dept_users.get(dept_id, []))

    def get_user(self, userid: str) -> DingtalkUser:
        return self._users[userid]


class FakeDeptWriter:
    def __init__(self) -> None:
        self.depts: dict[int, tuple[str, int | None]] = {}
        self.deactivated_with: set[int] | None = None
        self.user_depts: dict[str, list[int]] = {}

    def upsert_department(self, *, dept_id: int, name: str, parent_id: int | None) -> None:
        self.depts[dept_id] = (name, parent_id)

    def deactivate_missing(self, active_dept_ids: set[int]) -> None:
        self.deactivated_with = set(active_dept_ids)

    def set_user_departments(self, *, user_id: str, dept_ids: list[int]) -> None:
        self.user_depts[user_id] = list(dept_ids)


class FakeAccountWriter:
    def __init__(self) -> None:
        self.users: dict[str, str] = {}
        self._seq = 0

    def upsert_dingtalk_user(self, *, dingtalk_userid: str, name: str) -> str:
        if dingtalk_userid not in self.users:
            self._seq += 1
            self.users[dingtalk_userid] = f"user-{self._seq}"
        return self.users[dingtalk_userid]


def _tree_client() -> FakeClient:
    # 1(根) ─ 2(研发) ─ 4(前端组)
    #        └ 3(财务)
    children = {
        1: [DingtalkDept(2, "研发", 1), DingtalkDept(3, "财务", 1)],
        2: [DingtalkDept(4, "前端组", 2)],
    }
    dept_users = {2: ["u1"], 3: ["u1"], 4: ["u2"]}
    users = {
        "u1": DingtalkUser("u1", "张三", (2, 3)),
        "u2": DingtalkUser("u2", "李四", (4, 999)),  # 999 是未同步到的未知部门
    }
    return FakeClient(children, dept_users, users)


def test_collect_departments_walks_full_tree_including_synthetic_root() -> None:
    known = collect_departments(_tree_client())
    assert set(known) == {1, 2, 3, 4}
    assert known[1].parent_id is None  # 合成根
    assert known[4].parent_id == 2


def test_sync_upserts_all_departments_and_soft_deletes_against_active_set() -> None:
    departments = FakeDeptWriter()
    accounts = FakeAccountWriter()

    sync_organization(_tree_client(), departments, accounts)

    assert set(departments.depts) == {1, 2, 3, 4}
    assert departments.deactivated_with == {1, 2, 3, 4}


def test_sync_creates_one_account_per_user_and_assigns_known_departments() -> None:
    departments = FakeDeptWriter()
    accounts = FakeAccountWriter()

    summary = sync_organization(_tree_client(), departments, accounts)

    assert summary.department_count == 4
    assert summary.user_count == 2
    # 两个钉钉用户各建一个账号
    assert set(accounts.users) == {"u1", "u2"}
    u1_id = accounts.users["u1"]
    u2_id = accounts.users["u2"]
    # u1 归属 2、3（都在树里）
    assert sorted(departments.user_depts[u1_id]) == [2, 3]
    # u2 归属 4、999 → 未知的 999 被过滤，只留 4
    assert departments.user_depts[u2_id] == [4]


def test_sync_is_idempotent_in_counts() -> None:
    client = _tree_client()
    first = sync_organization(client, FakeDeptWriter(), FakeAccountWriter())
    second = sync_organization(client, FakeDeptWriter(), FakeAccountWriter())
    assert first == second
