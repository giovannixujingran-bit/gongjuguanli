# gen-models.ps1 —— Windows 版：从唯一源 event.schema.json 生成各层模型。
# 生成物落 shared/contracts/，文件头标「自动生成，勿手改」，禁止手改。
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")
python tools/generate_contracts.py
