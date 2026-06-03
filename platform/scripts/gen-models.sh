#!/usr/bin/env bash
# gen-models.sh —— 从唯一源 event.schema.json 生成各层模型。
# Schema 是唯一源（见 ../规划/总则/代码规范.md §三）：各层绝不手写字段，改字段只改 JSON Schema 再重跑本脚本。
# 生成物落在 shared/contracts/，文件头标「自动生成，勿手改」，禁止手改、被 lint/类型检查排除。
set -euo pipefail

cd "$(dirname "$0")/.."
SCHEMA="shared/schema/event.schema.json"
OUT="shared/contracts"
HEADER="# 自动生成，勿手改 —— 由 scripts/gen-models.sh 从 $SCHEMA 生成"

mkdir -p "$OUT"

# 后端 Pydantic v2 模型
uv run datamodel-codegen \
  --input "$SCHEMA" \
  --input-file-type jsonschema \
  --output-model-type pydantic_v2.BaseModel \
  --custom-file-header "$HEADER" \
  --output "$OUT/event_model.py"

# 前端 TS 类型（需 npx，Node 环境）
npx --yes json-schema-to-typescript "$SCHEMA" \
  --bannerComment "// 自动生成，勿手改 —— 由 scripts/gen-models.sh 从 $SCHEMA 生成" \
  > "$OUT/event.d.ts"

echo "生成完成：$OUT/event_model.py, $OUT/event.d.ts"
