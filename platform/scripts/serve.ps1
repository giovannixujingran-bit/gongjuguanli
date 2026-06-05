<#
.SYNOPSIS
  启停接入 API（本机开发用）。
.DESCRIPTION
  用法（在 platform 目录下）：
    .\scripts\serve.ps1 start      # 启动接入 API（后台），起来后探活 /health
    .\scripts\serve.ps1 stop       # 停止
    .\scripts\serve.ps1 status     # 查看状态
    .\scripts\serve.ps1 restart    # 重启
    .\scripts\serve.ps1 logs       # 跟踪日志

  配置全部读 platform/.env（不入库）。可在 .env 里覆盖：
    PLATFORM_PYTHON  用哪个 python 解释器（默认 python；本机离线环境填能匹配 .pydeps 的 3.12 路径）
    PLATFORM_HOST    监听地址（默认 127.0.0.1）
    PLATFORM_PORT    端口（默认 8000）
  脚本自动探测：若存在 platform/.pydeps，则把它加入 PYTHONPATH（离线依赖目录）。

  注意：这是开发用前台 dev-run（后台进程），不是常驻系统服务；机器重启后需重新 start。
  PostgreSQL 不由本脚本管理（独立部署/常驻）；start 前会探活 DB，连不上会提示。
  start 在探活 DB 后、起 API 前会自动应用数据库迁移（tools/migrate.py，幂等）；
  旧库首次需先「基线」一次，见 backend/storage/migrations/README.md。
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet('start', 'stop', 'status', 'restart', 'logs')]
  [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'
$PlatformDir = Split-Path -Parent $PSScriptRoot      # = platform/
Set-Location $PlatformDir

# ---- 载入 .env ----
$envFile = Join-Path $PlatformDir '.env'
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=][^=]*)=(.*)$') {
      [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
  }
}

$BindHost = if ($env:PLATFORM_HOST) { $env:PLATFORM_HOST } else { '127.0.0.1' }
$Port = if ($env:PLATFORM_PORT) { $env:PLATFORM_PORT } else { '8000' }
$Py = if ($env:PLATFORM_PYTHON) { $env:PLATFORM_PYTHON } else { 'python' }
$RunDir = Join-Path $PlatformDir '.run'
$PidFile = Join-Path $RunDir 'api.pid'
$LogFile = Join-Path $RunDir 'api.log'

# PYTHONPATH = 仓库根（+ .pydeps 若存在）
$pyPath = $PlatformDir
$pydeps = Join-Path $PlatformDir '.pydeps'
if (Test-Path $pydeps) { $pyPath = "$PlatformDir;$pydeps" }
$env:PYTHONPATH = $pyPath

function Get-ApiPid {
  if (Test-Path $PidFile) { return (Get-Content $PidFile | Select-Object -First 1) }
  return $null
}
function Test-ApiRunning {
  $p = Get-ApiPid
  if ($p) { return [bool](Get-Process -Id $p -ErrorAction SilentlyContinue) }
  return $false
}
function Test-DbReady {
  # 真探活：能否在 2s 内 TCP 连上 PostgreSQL。不通就别假装 API 起好了。
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $async = $client.BeginConnect($BindHost, 5432, $null, $null)
    $ok = $async.AsyncWaitHandle.WaitOne(2000)
    if ($ok) { $client.EndConnect($async) }
    $client.Close()
    return $ok
  }
  catch { return $false }
}

function Invoke-Migrations {
  # 起 API 前先把待办的建表/改表 SQL 应用上（幂等，已办的跳过）。
  # 失败即抛：宁可起不来也别让 API 跑在过期的库结构上。
  # 注意：旧库（表是早先 initdb/手工建的）首次需先「基线」，见 backend/storage/migrations/README.md。
  $migrate = Join-Path $PlatformDir 'tools\migrate.py'
  Write-Host "应用数据库迁移..."
  & $Py $migrate
  if ($LASTEXITCODE -ne 0) {
    throw "数据库迁移失败（退出码 $LASTEXITCODE）。旧库首次需先基线，见 backend/storage/migrations/README.md"
  }
}

function Start-Api {
  if (Test-ApiRunning) { Write-Host "已在运行 (PID $(Get-ApiPid)) -> http://${BindHost}:${Port}"; return }
  if (-not $env:DATABASE_URL) { throw "DATABASE_URL 未设置（检查 platform/.env）" }
  if (-not $env:AUTH_TOKEN_SECRET) { throw "AUTH_TOKEN_SECRET 未设置（检查 platform/.env）" }

  # 本机 dev：尽量自动拉起免安装 PG（失败不致命，下面以真实探活为准）。
  # 注意：不要把 pg.ps1 接进管道——pg.ps1 内部已用 Start-Process 起 pg_ctl，避免管道句柄继承挂死。
  try { & (Join-Path $PSScriptRoot 'pg.ps1') start }
  catch { Write-Warning "自动启动 PG 失败：$_" }
  if (-not (Test-DbReady)) {
    throw "PostgreSQL 不可达（${BindHost}:5432）。请先起 DB 再起 API：.\scripts\pg.ps1 start"
  }

  Invoke-Migrations

  New-Item -ItemType Directory -Force $RunDir | Out-Null

  $args = @('-m', 'uvicorn', 'backend.ingestion.app:app', '--host', $BindHost, '--port', $Port)
  $proc = Start-Process -FilePath $Py -ArgumentList $args `
    -WorkingDirectory $PlatformDir `
    -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err" `
    -WindowStyle Hidden -PassThru
  $proc.Id | Out-File -Encoding ascii $PidFile
  Write-Host "启动中 (PID $($proc.Id))..."

  # 探活 /health
  for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 700
    try {
      $r = Invoke-RestMethod -Uri "http://${BindHost}:${Port}/health" -TimeoutSec 2
      if ($r.status -eq 'ok') { Write-Host "API 就绪 -> http://${BindHost}:${Port}  (日志: $LogFile)"; return }
    }
    catch { }
  }
  Write-Warning "启动后 /health 未就绪，看日志：$LogFile.err"
}

function Stop-Api {
  $p = Get-ApiPid
  if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $p -Force
    Write-Host "已停止 (PID $p)"
  }
  else { Write-Host "未在运行" }
  Remove-Item $PidFile -ErrorAction SilentlyContinue
}

switch ($Action) {
  'start' { Start-Api }
  'stop' { Stop-Api }
  'restart' { Stop-Api; Start-Sleep -Milliseconds 500; Start-Api }
  'status' {
    if (Test-ApiRunning) { Write-Host "运行中 (PID $(Get-ApiPid)) -> http://${BindHost}:${Port}" }
    else { Write-Host "未运行" }
  }
  'logs' {
    if (Test-Path $LogFile) { Get-Content $LogFile -Tail 40 -Wait }
    else { Write-Host "暂无日志：$LogFile" }
  }
}
