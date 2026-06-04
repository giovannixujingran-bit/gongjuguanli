# collection —— 采集层

把「每一次使用」按统一契约送进接入 API。采集点放在自己掌控的层，不写在会被换的中转站上（[核心原则 3](../docs/architecture.md)）。

| 子目录 | 职责 | Phase |
|---|---|---|
| `sdk/` | 参考 SDK：工具自报的便捷封装（主路），归一化 token、回传 user_id、异步上报带缓冲重试 | 2a |
| `relay/` | 本地转发服务：OpenClaw / 黑盒工具改 base URL 指向它，旁路代采（兜底，非必经总闸） | 2b |

> 接入义务见 [数据端/接入契约](../docs/contract.md)。
