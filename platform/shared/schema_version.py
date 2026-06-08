"""数据契约版本的单一来源。

升版本只改这里一处：采集端（SDK / 自报实现）、接入层都从此模块取版本，
不再各自硬编码字面量。改动时仍需按 CLAUDE.md §3 四连动同步
schema-数据契约.md / event.schema.json / 建表 SQL，并把 CURRENT_SCHEMA_VERSION 升上来。
"""

from __future__ import annotations

# 当前契约版本：采集端构造事件时填它。
CURRENT_SCHEMA_VERSION = "v0.2"

# 接入层「认识」的版本集合。收到不在此集合内的版本不拒收（守「不阻断入库」），
# 但会告警，提示分析层/运维这是一条本平台尚未支持解析的版本。
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"v0.2"})
