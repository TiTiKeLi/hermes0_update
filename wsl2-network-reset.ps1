# WSL2 Network Reset Script
# 在系统从休眠/睡眠恢复后执行，强制重置WSL2网络栈
# 用法: powershell -ExecutionPolicy Bypass -File wsl2-network-reset.ps1

$ErrorActionPreference = "SilentlyContinue"
$logFile = "$PSScriptRoot\wsl2-network-reset.log"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Log($msg) {
    "[$ts] $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
    Write-Host "[$ts] $msg"
}

Log "=== WSL2 Network Reset ==="

# Step 1: 等待Docker Desktop恢复
Log "Waiting for Docker Desktop..."
$waitSeconds = 0
while ($waitSeconds -lt 60) {
    $docker = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
    if ($docker) { break }
    Start-Sleep -Seconds 2
    $waitSeconds += 2
}
if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
    Log "Starting Docker Desktop..."
    Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    Start-Sleep -Seconds 20
}
Log "Docker Desktop: OK"

# Step 2: WSL2网络重置
Log "Resetting WSL2 network..."
try {
    # restart WSL2 VM networking
    wsl -d Ubuntu -e sudo ip link set eth0 down
    wsl -d Ubuntu -e sudo ip link set eth0 up
    Start-Sleep -Seconds 3
    wsl -d Ubuntu -e sudo dhclient eth0 2>$null
    Log "WSL2 network reset: OK"
} catch {
    Log "WSL2 network reset failed (non-critical): $_"
}

# Step 3: 确认Docker daemon可用
Log "Waiting for Docker daemon..."
$dockerReady = $false
for ($i = 0; $i -lt 30; $i++) {
    $test = docker ps 2>$null
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $dockerReady) {
    Log "ERROR: Docker daemon not available after 60s"
    exit 1
}
Log "Docker daemon: OK"

# Step 4: 重启Hermes容器
Log "Restarting Hermes container..."
$restartResult = docker restart hermes 2>&1
if ($LASTEXITCODE -eq 0) {
    Log "Hermes container restart: OK"
} else {
    Log "Hermes container restart failed, trying re-create..."
    docker stop hermes 2>$null
    docker rm hermes 2>$null
    docker run -d --name hermes `
        --restart unless-stopped `
        -p 8642:8642 `
        -v "$env:USERPROFILE\.hermes:/opt/data" `
        --dns 8.8.8.8 `
        --dns 223.5.5.5 `
        --add-host host.docker.internal:host-gateway `
        hermes-agent:latest gateway run
    if ($LASTEXITCODE -eq 0) {
        Log "Hermes container re-created: OK"
    } else {
        Log "ERROR: Hermes container re-creation failed"
        exit 1
    }
}

Start-Sleep -Seconds 8

# Step 5: 验证
Log "Verifying Hermes health..."
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8643/api/status" -TimeoutSec 10
    $wechatOk = $health.wechat -eq "connected"
    Log "Gateway: $($health.gateway)"
    Log "WeChat: $($health.wechat)"
    if ($wechatOk) {
        Log "=== RECOVERY COMPLETE - WeChat connected ==="
    } else {
        Log "=== RECOVERY PARTIAL - WeChat $($health.wechat) ==="
    }
} catch {
    Log "Health check failed - dashboard may still be starting: $_"
    Log "=== RECOVERY COMPLETE (unverified) ==="
}
