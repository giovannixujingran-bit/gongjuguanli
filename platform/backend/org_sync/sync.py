from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.org_sync.client import _ROOT_DEPT_ID, DingtalkClient, DingtalkDept


class DepartmentWriter(Protocol):
    """落库写入接口（部门 + 人↔部门）。

    只收基本类型、不依赖 org_sync 的数据类（DingtalkDept），这样 storage 层实现它时
    无需反向 import 上层（守单向分层）；DTO 拆包在本层（org_sync）完成。
    """

    def upsert_department(self, *, dept_id: int, name: str, parent_id: int | None) -> None:
        """有则更新、无则插入；并标记 active=true、刷新 synced_at。"""

    def deactivate_missing(self, active_dept_ids: set[int]) -> None:
        """把本轮没见到的部门软删（active=false），不硬删（决策 #38/P6）。"""

    def set_user_departments(self, *, user_id: str, dept_ids: list[int]) -> None:
        """按钉钉归属整体覆盖某人的部门集合。"""


class AccountWriter(Protocol):
    """账号写入接口。由 auth 层实现。"""

    def upsert_dingtalk_user(self, *, dingtalk_userid: str, name: str) -> str:
        """按 dingtalk_userid 有则更新、无则建账号（无密码，P2）；返回平台 user_id。"""


@dataclass(frozen=True)
class SyncSummary:
    """一次同步的结果摘要。"""

    department_count: int
    user_count: int


def collect_departments(
    client: DingtalkClient, root_id: int = _ROOT_DEPT_ID
) -> dict[int, DingtalkDept]:
    """从根部门起逐层向下，收集整棵部门树（钉钉一次只返回下一级，故需 BFS）。

    根部门（id=1）本身不在 listsub 结果里，合成一个占位根，保证后续人员的
    部门归属若指向根时不会悬空。靠 known 去重，天然防环。
    """
    known: dict[int, DingtalkDept] = {
        root_id: DingtalkDept(dept_id=root_id, name="根部门", parent_id=None)
    }
    queue: list[int] = [root_id]
    while queue:
        parent_id = queue.pop()
        for dept in client.list_sub_departments(parent_id):
            if dept.dept_id not in known:
                known[dept.dept_id] = dept
                queue.append(dept.dept_id)
    return known


def sync_organization(
    client: DingtalkClient,
    departments: DepartmentWriter,
    accounts: AccountWriter,
    *,
    root_id: int = _ROOT_DEPT_ID,
) -> SyncSummary:
    """跑一次组织同步：部门树 → 落部门 → 软删失活 → 收人 → 落账号 + 人↔部门。

    幂等：整轮是覆盖式 upsert，重复跑结果一致。
    """
    depts = collect_departments(client, root_id)
    for dept in depts.values():
        departments.upsert_department(
            dept_id=dept.dept_id, name=dept.name, parent_id=dept.parent_id
        )
    departments.deactivate_missing(set(depts))

    userids: set[str] = set()
    for dept_id in depts:
        userids.update(client.list_department_user_ids(dept_id))

    for userid in sorted(userids):
        user = client.get_user(userid)
        user_id = accounts.upsert_dingtalk_user(dingtalk_userid=user.userid, name=user.name)
        # 只挂到本轮确实同步到的部门，避免指向未知部门造成悬空引用
        valid_dept_ids = [dept_id for dept_id in user.dept_ids if dept_id in depts]
        departments.set_user_departments(user_id=user_id, dept_ids=valid_dept_ids)

    return SyncSummary(department_count=len(depts), user_count=len(userids))
