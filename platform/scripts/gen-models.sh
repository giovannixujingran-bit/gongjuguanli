#!/usr/bin/env bash
# gen-models.sh —— 从唯一源 event.schema.json 生成各层模型。
# Schema 是唯一源（见 ../docs/code-standards.md §三）：各层绝不手写字段，改字段只改 JSON Schema 再重跑本脚本。
# 生成物落在 shared/contracts/，文件头标「自动生成，勿手改」，禁止手改、被 lint/类型检查排除。
set -euo pipefail

cd "$(dirname "$0")/.."
python tools/generate_contracts.py
