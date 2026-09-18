# SPDX-License-Identifier: MIT
<#
.SYNOPSIS
  Register a per-minute Scheduled Task for RoutineScheduler tick.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\windows\register_routine_tick.ps1
  powershell -File scripts\windows\register_routine_tick.ps1 -Mode live
#>
[CmdletBinding()]
param(
  [string]$TaskName = "XiongbaoAgent-RoutineTick",
  [ValidateSet("dry", "test", "live")]
  [string]$Mode = "dry",
  [string]$Root = "artifacts\teach_routine",
  [string]$PythonExe = "",
  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if (-not $PythonExe) {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) { throw "python not found on PATH; pass -PythonExe" }
  $PythonExe = $py.Source
}

$tickArgs = @(
  "-S",
  "-m", "octop.contrib.workbuddy.teach_cli",
  "--root", $Root,
  "tick",
  "--mode", $Mode
)

# schtasks /tr expects a single command string
$tr = "`"$PythonExe`" $($tickArgs -join ' ')"
$work = $RepoRoot

Write-Host "RepoRoot : $RepoRoot"
Write-Host "Python   : $PythonExe"
Write-Host "Task     : $TaskName"
Write-Host "Command  : $tr"
Write-Host "WorkDir  : $work"
Write-Host "Mode     : $Mode"

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  Write-Host "Removed existing task $TaskName"
}

$action = New-ScheduledTaskAction `
  -Execute $PythonExe `
  -Argument ($tickArgs -join " ") `
  -WorkingDirectory $work

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Minutes 1) `
  -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -MultipleInstances IgnoreNew

# Inject PYTHONPATH via environment for the task process:
# ScheduledTask env is limited; wrap via cmd /c set && python
$envLine = "set PYTHONPATH=$RepoRoot&& `"$PythonExe`" $($tickArgs -join ' ')"
$action = New-ScheduledTaskAction `
  -Execute "cmd.exe" `
  -Argument "/c $envLine" `
  -WorkingDirectory $work

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -Description "xiongbao-agent RoutineScheduler tick ($Mode)" `
  -User $env:USERNAME `
  | Out-Null

Write-Host "OK registered: $TaskName (every 1 min, mode=$Mode)"
Write-Host "Verify: Get-ScheduledTask -TaskName $TaskName"
Write-Host "Run now: Start-ScheduledTask -TaskName $TaskName"
Write-Host "Remove:  powershell -File scripts\windows\unregister_routine_tick.ps1"
