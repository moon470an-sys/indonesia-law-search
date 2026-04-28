<#
.SYNOPSIS
    Register a Windows Task Scheduler entry that runs daily_update.py
    every morning at 09:00 KST.

.DESCRIPTION
    Creates (or replaces) a task named "JDIH-Daily-Update" under the
    current user. The task runs python with the project's daily_update
    script, with cwd pinned to the project root so relative paths in the
    crawler resolve.

    Run once from an elevated PowerShell:
        cd "C:\Users\yoonseok.moon\OneDrive - (주) ST International\Projects\인도네시아 법령"
        powershell -ExecutionPolicy Bypass -File scripts\install_daily_task.ps1

    Optional environment overrides (set BEFORE running install or
    persistently via "Edit Variables" in Windows):
        JDIH_SMTP_HOST = smtp.gmail.com
        JDIH_SMTP_PORT = 587
        JDIH_SMTP_USER = moon470an@gmail.com
        JDIH_SMTP_PASSWORD = <16-char Gmail app password>
        JDIH_EMAIL_FROM = moon470an@gmail.com
        JDIH_EMAIL_TO = yoonseok.moon@sticorp.co.kr
#>

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$pythonExe = (Get-Command python).Source
$scriptArgs = "-m scripts.daily_update"

Write-Host "Project root : $projectRoot"
Write-Host "Python       : $pythonExe"
Write-Host "Script args  : $scriptArgs"

$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument $scriptArgs `
    -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At 09:00

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 60)

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Daily Indonesian-law incremental crawl + email summary (09:00 KST)"

Register-ScheduledTask -TaskName "JDIH-Daily-Update" -InputObject $task -Force | Out-Null

Write-Host ""
Write-Host "✅ Task registered: JDIH-Daily-Update (daily 09:00)"
Write-Host ""
Write-Host "Verify with:"
Write-Host "    Get-ScheduledTask -TaskName JDIH-Daily-Update"
Write-Host "    Start-ScheduledTask -TaskName JDIH-Daily-Update   # run immediately"
Write-Host "    Get-ScheduledTaskInfo -TaskName JDIH-Daily-Update"
Write-Host ""
Write-Host "Last-run log lives at:"
Write-Host "    $projectRoot\data\pending\last_daily_log.txt"
