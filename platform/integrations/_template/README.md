# _template —— 真实工具试点模板

新工具接入的起点：复制本目录，改名为工具目录，在工具注册表登记拿 `tool_id`，再按
[pilot_checklist.md](pilot_checklist.md) 执行试点。工具本体不放这里，本目录只放接入说明、
配置样例、验证记录和回滚方案。

Phase 2C 只选择**低风险、可改代码、调用路径清楚**的真实工具。记录圈一事实、token、
status、duration，以及 `metadata.entry_source` / `metadata.auth_method`；`input_content` /
`output_content` 原文可按需记录（已放开，读取侧权限待定，见 [pilot_checklist.md](pilot_checklist.md)）。

## 文件

- [pilot_checklist.md](pilot_checklist.md)：试点准入、实施、验收、回滚清单。
- [tool_config.example.json](tool_config.example.json)：接入配置样例，复制后按工具实际情况填写。
