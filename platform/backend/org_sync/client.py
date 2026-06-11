from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx

# 钉钉组织同步用的是「经典通讯录接口」（topapi，oapi.dingtalk.com）：
#   - 取 access_token：GET  /gettoken
#   - 子部门列表：     POST /topapi/v2/department/listsub
#   - 部门成员 userid：POST /topapi/user/listid
#   - 用户详情：       POST /topapi/v2/user/get
# 官方新 SDK（api.dingtalk.com）不覆盖部门树遍历，故直接用 httpx 调（决策 #38 实现说明）。
_DEFAULT_BASE_URL = "https://oapi.dingtalk.com"
_ROOT_DEPT_ID = 1
# access_token 有效期约 7200s；提前 5 分钟刷新，避免边界过期。
_TOKEN_REFRESH_MARGIN_SECONDS = 300


@dataclass(frozen=True)
class DingtalkDept:
    """一个钉钉部门（部门树的一个节点）。"""

    dept_id: int
    name: str
    parent_id: int | None


@dataclass(frozen=True)
class DingtalkUser:
    """一个钉钉员工（含其归属部门）。"""

    userid: str
    name: str
    dept_ids: tuple[int, ...]


class DingtalkApiError(Exception):
    """钉钉接口返回了非零 errcode，或响应结构不符合预期。"""

    def __init__(self, endpoint: str, errcode: int, errmsg: str) -> None:
        super().__init__(f"dingtalk api {endpoint} failed: [{errcode}] {errmsg}")
        self.endpoint = endpoint
        self.errcode = errcode
        self.errmsg = errmsg


class DingtalkClient(Protocol):
    """组织同步依赖的钉钉读能力（抽象，便于 mock 单测、便于将来换实现）。"""

    def list_sub_departments(self, parent_id: int) -> list[DingtalkDept]:
        """列出 parent_id 的直接子部门（钉钉一次只返回下一级）。"""

    def list_department_user_ids(self, dept_id: int) -> list[str]:
        """列出某部门下所有成员的 userid。"""

    def get_user(self, userid: str) -> DingtalkUser:
        """取某员工的详情（姓名 + 归属部门）。"""


def _require_dict(endpoint: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DingtalkApiError(endpoint, -1, f"unexpected response type: {type(value).__name__}")
    return value


def _require_ok(endpoint: str, payload: dict[str, object]) -> dict[str, object]:
    errcode_raw = payload.get("errcode", 0)
    errcode = errcode_raw if isinstance(errcode_raw, int) else -1
    if errcode != 0:
        errmsg = payload.get("errmsg")
        raise DingtalkApiError(endpoint, errcode, str(errmsg) if errmsg is not None else "")
    return payload


class HttpxDingtalkClient:
    """用 httpx 调经典通讯录接口的 DingtalkClient 实现（带 access_token 缓存）。

    凭据走配置/环境变量，不硬编码（决策 #34 密钥纪律）。注入 httpx.Client 便于复用连接。
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        http: httpx.Client | None = None,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=10.0)
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    def _access_token(self) -> str:
        if self._token is not None and time.monotonic() < self._token_expires_at:
            return self._token
        endpoint = "/gettoken"
        response = self._http.get(
            f"{self._base_url}{endpoint}",
            params={"appkey": self._client_id, "appsecret": self._client_secret},
        )
        response.raise_for_status()
        payload = _require_ok(endpoint, _require_dict(endpoint, response.json()))
        token = payload.get("access_token")
        expires_in = payload.get("expires_in", 7200)
        if not isinstance(token, str):
            raise DingtalkApiError(endpoint, -1, "missing access_token")
        ttl = expires_in if isinstance(expires_in, int) else 7200
        self._token = token
        self._token_expires_at = time.monotonic() + max(ttl - _TOKEN_REFRESH_MARGIN_SECONDS, 0)
        return token

    def _post(self, endpoint: str, body: dict[str, object]) -> dict[str, object]:
        response = self._http.post(
            f"{self._base_url}{endpoint}",
            params={"access_token": self._access_token()},
            json=body,
        )
        response.raise_for_status()
        return _require_ok(endpoint, _require_dict(endpoint, response.json()))

    def list_sub_departments(self, parent_id: int) -> list[DingtalkDept]:
        endpoint = "/topapi/v2/department/listsub"
        payload = self._post(endpoint, {"dept_id": parent_id})
        result = payload.get("result")
        if not isinstance(result, list):
            return []
        depts: list[DingtalkDept] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            dept_id = item.get("dept_id")
            name = item.get("name")
            parent = item.get("parent_id")
            if isinstance(dept_id, int) and isinstance(name, str):
                depts.append(
                    DingtalkDept(
                        dept_id=dept_id,
                        name=name,
                        parent_id=parent if isinstance(parent, int) else None,
                    )
                )
        return depts

    def list_department_user_ids(self, dept_id: int) -> list[str]:
        endpoint = "/topapi/user/listid"
        payload = self._post(endpoint, {"dept_id": dept_id})
        result = payload.get("result")
        if not isinstance(result, dict):
            return []
        userid_list = result.get("userid_list")
        if not isinstance(userid_list, list):
            return []
        return [uid for uid in userid_list if isinstance(uid, str)]

    def get_user(self, userid: str) -> DingtalkUser:
        endpoint = "/topapi/v2/user/get"
        payload = self._post(endpoint, {"userid": userid})
        result = payload.get("result")
        if not isinstance(result, dict):
            raise DingtalkApiError(endpoint, -1, "missing result")
        name = result.get("name")
        dept_id_list = result.get("dept_id_list")
        dept_ids: tuple[int, ...] = ()
        if isinstance(dept_id_list, list):
            dept_ids = tuple(d for d in dept_id_list if isinstance(d, int))
        return DingtalkUser(
            userid=userid,
            name=str(name) if name is not None else userid,
            dept_ids=dept_ids,
        )


__all__ = [
    "_ROOT_DEPT_ID",
    "DingtalkApiError",
    "DingtalkClient",
    "DingtalkDept",
    "DingtalkUser",
    "HttpxDingtalkClient",
]
