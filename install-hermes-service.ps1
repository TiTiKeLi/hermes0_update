# Hermes Connection Persistence - Installation Script
# 以管理员身份运行: powershell -ExecutionPolicy Bypass -File install-hermes-service.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"
$HERMES_HOME = $PSScriptRoot
$TASK_NAME_POWER = "HermesResumeRecovery"
$TASK_NAME_DAEMON = "HermesConnectionDaemon"
$TASK_NAME_WATCHDOG = "HermesDailyWatchdog"

function Confirm-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-Banner {
    Clear-Host
    Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║     Hermes Connection Persistence Installer v1.0    ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Install-ResumeTask {
    Write-Host "📋 Installing Resume Recovery Task..." -ForegroundColor Yellow

    # 先删除旧任务（如果存在）
    schtasks /Delete /TN "$TASK_NAME_POWER" /F 2>$null

    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$HERMES_HOME\wsl2-network-reset.ps1`""

    $trigger = New-ScheduledTaskTrigger -AtStartup
    $trigger.Delay = "PT30S"

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
        -Priority 7

    Register-ScheduledTask -TaskName $TASK_NAME_POWER `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Limited `
        -User $env:USERNAME `
        -Force

    Write-Host "  ✅ Resume Recovery Task: $TASK_NAME_POWER" -ForegroundColor Green
}

function Install-DaemonTask {
    Write-Host "📋 Installing Connection Persistence Daemon (startup)..." -ForegroundColor Yellow

    schtasks /Delete /TN "$TASK_NAME_DAEMON" /F 2>$null

    $action = New-ScheduledTaskAction -Execute "python" `
        -Argument "-u `"$HERMES_HOME\connection_persister.py`" --daemon" `
        -WorkingDirectory $HERMES_HOME

    $trigger = New-ScheduledTaskTrigger -AtStartup
    $trigger.Delay = "PT45S"

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit 0 `
        -Priority 5

    Register-ScheduledTask -TaskName $TASK_NAME_DAEMON `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Limited `
        -User $env:USERNAME `
        -Force

    Write-Host "  ✅ Daemon Task: $TASK_NAME_DAEMON" -ForegroundColor Green
}

function Install-WeeklyWatchdog {
    Write-Host "📋 Installing Weekly Watchdog Task..." -ForegroundColor Yellow

    schtasks /Delete /TN "$TASK_NAME_WATCHDOG" /F 2>$null

    $action = New-ScheduledTaskAction -Execute "python" `
        -Argument "-u `"$HERMES_HOME\connection_persister.py`" --recover" `
        -WorkingDirectory $HERMES_HOME

    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 03:00AM

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
        -Priority 7

    Register-ScheduledTask -TaskName $TASK_NAME_WATCHDOG `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Limited `
        -User $env:USERNAME `
        -Force

    Write-Host "  ✅ Weekly Watchdog Task: $TASK_NAME_WATCHDOG" -ForegroundColor Green
}

function Configure-DockerRestart {
    Write-Host "📋 Configuring Docker container restart policy..." -ForegroundColor Yellow
    docker update --restart unless-stopped hermes 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Hermes container restart policy: unless-stopped" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Hermes container not running yet - will be applied on first start" -ForegroundColor Gray
    }
}

function Build-HealthcheckImage {
    Write-Host "📋 Building healthcheck-enabled Hermes image..." -ForegroundColor Yellow
    docker build -t hermes-agent:healthcheck -f "$HERMES_HOME\Dockerfile" "$HERMES_HOME" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Healthcheck image built: hermes-agent:healthcheck" -ForegroundColor Green
        return $true
    } else {
        Write-Host "  ⚠️  Healthcheck image build failed - will use standard image" -ForegroundColor Yellow
        return $false
    }
}

function Install-DockerCompose {
    Write-Host "📋 Updating docker-compose.yml with healthcheck..." -ForegroundColor Yellow
    $composePath = "$HERMES_HOME\docker-compose.yml"
    if (Test-Path $composePath) {
        $content = Get-Content $composePath -Raw
        if (-not ($content -match "healthcheck")) {
            $extra = @"

  healthcheck:
    test: ["CMD", "bash", "/opt/data/healthcheck.sh"]
    interval: 60s
    timeout: 10s
    start_period: 30s
    retries: 3
"@
            $updated = $content -replace "restart: unless-stopped", "restart: unless-stopped$extra"
            Set-Content -Path $composePath -Value $updated
            Write-Host "  ✅ docker-compose.yml updated with healthcheck" -ForegroundColor Green
        } else {
            Write-Host "  ✅ docker-compose.yml already has healthcheck" -ForegroundColor Green
        }
    }
}

function Test-Installation {
    Write-Host ""
    Write-Host "🔍 Verifying Installation..." -ForegroundColor Yellow

    Write-Host "  Tasks created:"
    schtasks /Query /TN "$TASK_NAME_POWER" /FO LIST /V 2>$null | Select-String "TaskName|Status|Next Run"
    schtasks /Query /TN "$TASK_NAME_DAEMON" /FO LIST /V 2>$null | Select-String "TaskName|Status|Next Run"
    schtasks /Query /TN "$TASK_NAME_WATCHDOG" /FO LIST /V 2>$null | Select-String "TaskName|Status|Next Run"

    Write-Host ""
    Write-Host "  Files installed:" -ForegroundColor Yellow
    Get-ChildItem "$HERMES_HOME" -Filter *.ps1,*.py,*.sh | Select-Object Name,Length | Format-Table -AutoSize
}

function Show-Summary {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                 Installation Complete                ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "✅ Resume Recovery Task   - 系统唤醒后自动重连" -ForegroundColor Green
    Write-Host "✅ Connection Daemon       - 每30秒心跳检测 + 自动恢复" -ForegroundColor Green
    Write-Host "✅ Weekly Watchdog         - 每周日凌晨3点深度清理" -ForegroundColor Green
    Write-Host "✅ Docker Restart Policy   - unless-stopped" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 管理命令:" -ForegroundColor Cyan
    Write-Host "  查看任务: schtasks /Query /TN Hermes* /V"
    Write-Host "  运行恢复: $HERMES_HOME\wsl2-network-reset.ps1"
    Write-Host "  手动检查: python $HERMES_HOME\connection_persister.py --check"
    Write-Host "  手动恢复: python $HERMES_HOME\connection_persister.py --recover"
    Write-Host ""
    Write-Host "💡 测试休眠恢复:" -ForegroundColor Gray
    Write-Host "  powercfg /hibernate on   (启用休眠)"
    Write-Host "  shutdown /h              (进入休眠)"
    Write-Host ""
}

# ═══════ MAIN ═══════════

Write-Banner

if (-not (Confirm-Admin)) {
    Write-Host "❌ Please run as Administrator (右键 → 以管理员身份运行)" -ForegroundColor Red
    exit 1
}

Write-Host "🔧 Hermes Home: $HERMES_HOME" -ForegroundColor Cyan
Write-Host ""

# Step 1: Install scheduled tasks
Install-ResumeTask
Install-DaemonTask
Install-WeeklyWatchdog

# Step 2: Configure Docker
Configure-DockerRestart

# Step 3: Build healthcheck image (optional)
$hasHealthcheck = Build-HealthcheckImage

# Step 4: Update compose file
Install-DockerCompose

# Step 5: Verify
Test-Installation

# Done
Show-Summary

if (-not $hasHealthcheck) {
    Write-Host "⚠️  Healthcheck image build failed. To retry manually:" -ForegroundColor Yellow
    Write-Host "   docker build -t hermes-agent:healthcheck -f `"$HERMES_HOME\Dockerfile`" `"$HERMES_HOME`"" -ForegroundColor Gray
}
