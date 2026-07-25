# 重启 Hermes 容器（使 --network=host 生效）
# 在 PowerShell (管理员) 中运行:
#   powershell -ExecutionPolicy Bypass -File "C:\Users\Lsc\.hermes\restart-hermes.ps1"

$HERMES_HOME = "C:\Users\Lsc\.hermes"
cd $HERMES_HOME

Write-Host "=== 停止 Hermes ===" -ForegroundColor Cyan
wsl -d Ubuntu -- docker compose -f "$HERMES_HOME\docker-compose.yml" down

Write-Host "=== 启动 Hermes ===" -ForegroundColor Cyan
wsl -d Ubuntu -- docker compose -f "$HERMES_HOME\docker-compose.yml" up -d

Write-Host "=== 等待就绪 ===" -ForegroundColor Cyan
Start-Sleep -Seconds 10

Write-Host "=== 检查状态 ===" -ForegroundColor Cyan
wsl -d Ubuntu -- docker ps --filter name=hermes --format "table {{.Names}}\t{{.Status}}"

Write-Host "✅ 完成" -ForegroundColor Green
