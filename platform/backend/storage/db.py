from __future__ import annotations

import os

import psycopg
from psycopg import Connection
from psycopg.rows import TupleRow

# DB 连接默认超时（秒）。
# 目的：PostgreSQL 不可达时 *快速失败* 而非无限等待——否则接入 API 的请求线程会被
# 一直占住，连发几条就能把线程池占满，最终连 /health 都假死（曾因 PG 未启动踩到）。
# 可用环境变量 DB_CONNECT_TIMEOUT 覆盖。
DEFAULT_CONNECT_TIMEOUT = 5


def _connect_timeout() -> int:
    raw = os.environ.get("DB_CONNECT_TIMEOUT")
    if raw is None or not raw.strip():
        return DEFAULT_CONNECT_TIMEOUT
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_CONNECT_TIMEOUT
    return value if value > 0 else DEFAULT_CONNECT_TIMEOUT


def connect(database_url: str) -> Connection[TupleRow]:
    """统一的 PostgreSQL 连接入口（带连接超时）。

    所有仓库都应经此连接，确保 DB 不可达时快速失败。不要再直接调用
    ``psycopg.connect``（默认无连接超时，会无限挂起）。
    """
    return psycopg.connect(database_url, connect_timeout=_connect_timeout())
