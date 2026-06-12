<#
.SYNOPSIS
  安装/卸载「登录时自动启动平台（PG + 接入 API）」的计划任务。
.DESCRIPTION
  用法（在 platform 目录下）：
    .\scripts\autostart.ps1 install   # 注册：当前用户登录时自动 serve start
    .\scripts\autostart.ps1 remove    # 卸载
    .\scripts\autostart.ps1 status    # 查看是否已注册

  原理：建一个「用户登录触发」的计划任务，隐藏窗口跑 serve.ps1 start（优先用 PowerShell 7 / pwsh）。
  免安装 PG 不是 Windows 服务，登录后由 serve.ps1 顺带把 PG 带起来。
  仅当前用户、登录后生效（机器重启到登录界面前不会起，够本机 dev 用）。
  要让 PG 在登录前就常驻，得把 PostgreSQL 注册成 Windows 服务（需管理员），另行处理。
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet('install', 'remove', 'status')]
  [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'
$ServePs1 = Join-Path $PSScriptRoot 'serve.ps1'
$TaskName = 'Platform-Ingestion-Autostart'
$User = "$env:USERDOMAIN\$env:USERNAME"

switch ($Action) {
  'install' {
    $pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    $shell = if ($pwsh) { $pwsh.Source } else { 'powershell.exe' }
    $taskAction = New-ScheduledTaskAction -Execute $shell `
      -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ServePs1`" start"
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
      -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $trigger `
      -Settings $settings -RunLevel Limited -Force | Out-Null
    Write-Host "已注册登录自启：$TaskName（用户 $User，Shell $shell）"
  }
  'remove' {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "已卸载：$TaskName"
  }
  'status' {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) { Write-Host "已注册：$TaskName（状态 $($t.State)）" } else { Write-Host "未注册" }
  }
}
