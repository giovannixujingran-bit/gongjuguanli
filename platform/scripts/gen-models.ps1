# gen-models.ps1 —— Windows 版：从唯一源 event.schema.json 生成各层模型。
# 见 gen-models.sh 的说明。生成物落 shared/contracts/，文件头标「自动生成，勿手改」，禁止手改。
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")
$Schema = "shared/schema/event.schema.json"
$Out    = "shared/contracts"
$Header = "# 自动生成，勿手改 —— 由 scripts/gen-models.ps1 从 $Schema 生成"

if (-not (Test-Path $Out)) { New-Item -ItemType Directory $Out | Out-Null }

# 后端 Pydantic v2 模型
uv run datamodel-codegen `
  --input $Schema `
  --input-file-type jsonschema `
  --output-model-type pydantic_v2.BaseModel `
  --custom-file-header $Header `
  --output "$Out/event_model.py"

# 前端 TS 类型
npx --yes json-schema-to-typescript $Schema `
  --bannerComment "// 自动生成，勿手改 —— 由 scripts/gen-models.ps1 从 $Schema 生成" `
  > "$Out/event.d.ts"

Write-Host "生成完成：$Out/event_model.py, $Out/event.d.ts"
