<#
.SYNOPSIS
  启停本机免安装 PostgreSQL（dev 用）。
.DESCRIPTION
  用法（在 platform 目录下）：
    .\scripts\pg.ps1 start    # 启动 PG（若已在跑则跳过）
    .\scripts\pg.ps1 stop     # 停止 PG
    .\scripts\pg.ps1 status   # 查看是否可连接

  路径读 platform/.env（可覆盖，缺省指向 D:\pg-portable）：
    PG_BIN   含 pg_ctl.exe / pg_isready.exe 的目录（默认 D:\pg-portable\pgsql\bin）
    PG_DATA  数据目录（默认 D:\pg-portable\data）
  探活地址固定 127.0.0.1:5432（PG 默认）。

  注意：这是本机 dev 起法；正式部署用 docker-compose（见 docs/execution-plan.md）。
  机器重启后 PG 不会自动恢复——要么每次 start，要么把 PG 注册成 Windows 服务（见 execution-plan）。
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet('start', 'stop', 'status')]
  [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'
$PlatformDir = Split-Path -Parent $PSScriptRoot

# ---- 载入 .env ----
$envFile = Join-Path $PlatformDir '.env'
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=][^=]*)=(.*)$') {
      [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
  }
}

$PgBin = if ($env:PG_BIN) { $env:PG_BIN } else { 'D:\pg-portable\pgsql\bin' }
$PgData = if ($env:PG_DATA) { $env:PG_DATA } else { 'D:\pg-portable\data' }
$PgCtl = Join-Path $PgBin 'pg_ctl.exe'
$PgIsReady = Join-Path $PgBin 'pg_isready.exe'
$LogFile = Join-Path $PgData 'server.log'

function Test-PgReady {
  if (-not (Test-Path $PgIsReady)) { return $false }
  & $PgIsReady -h 127.0.0.1 -p 5432 -q | Out-Null
  return ($LASTEXITCODE -eq 0)
}

function Assert-PgTools {
  if (-not (Test-Path $PgCtl)) {
    throw "找不到 pg_ctl：$PgCtl（检查 .env 的 PG_BIN，或确认免安装 PG 的安装路径）"
  }
}

switch ($Action) {
  'start' {
    if (Test-PgReady) { Write-Host "PG 已在运行 (127.0.0.1:5432)"; break }
    Assert-PgTools
    # 关键：用 Start-Process + 文件重定向起 pg_ctl，绝不接 PowerShell 管道。
    # 否则常驻的 postgres 会继承管道写端、永不关闭，管道读端永远等不到 EOF 而挂死。
    $ctlOut = Join-Path $PgData 'pg_ctl.out'
    Start-Process -FilePath $PgCtl `
      -ArgumentList @('-D', $PgData, '-l', $LogFile, 'start') `
      -NoNewWindow `
      -RedirectStandardOutput $ctlOut -RedirectStandardError "$ctlOut.err"
    for ($i = 0; $i -lt 20; $i++) {
      Start-Sleep -Milliseconds 500
      if (Test-PgReady) { Write-Host "PG 就绪 (127.0.0.1:5432)"; break }
    }
    if (-not (Test-PgReady)) { Write-Warning "PG 启动后仍探活失败，看日志：$LogFile" }
  }
  'stop' {
    Assert-PgTools
    & $PgCtl -D $PgData -m fast stop
    Write-Host "PG 已停止"
  }
  'status' {
    if (Test-PgReady) { Write-Host "PG 运行中 (127.0.0.1:5432)" } else { Write-Host "PG 未运行" }
  }
}
