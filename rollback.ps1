# Hermes GUI 回滚脚本
# 用法: .\rollback.ps1 v2.0

param(
    [Parameter(Mandatory=$true)]
    [string]$Version
)

$versionsDir = "C:\Users\Lsc\.hermes\versions"
$hermesDir = "C:\Users\Lsc\.hermes"
$targetDir = "$versionsDir\$Version"

if (-not (Test-Path $targetDir)) {
    Write-Host "Error: Version $Version not found in $versionsDir" -ForegroundColor Red
    Write-Host "Available versions:" -ForegroundColor Yellow
    Get-ChildItem $versionsDir -Directory | ForEach-Object { Write-Host "  $($_.Name)" }
    exit 1
}

Write-Host "Rolling back to version $Version..." -ForegroundColor Cyan

# Backup current version
$currentVersion = "v" + (Get-Date -Format "yyyy-MM-dd_HHmmss")
$currentBackup = "$versionsDir\$currentVersion"
New-Item -ItemType Directory -Path $currentBackup -Force | Out-Null
Copy-Item "$hermesDir\gui.html" "$currentBackup\gui.html" -Force
Copy-Item "$hermesDir\gui.py" "$currentBackup\gui.py" -Force
Write-Host "Current version backed up as: $currentVersion" -ForegroundColor Green

# Restore target version
Copy-Item "$targetDir\gui.html" "$hermesDir\gui.html" -Force
Copy-Item "$targetDir\gui.py" "$hermesDir\gui.py" -Force
Write-Host "Files restored from $Version" -ForegroundColor Green

# Copy to container
docker cp "$hermesDir\gui.html" hermes:/opt/data/gui.html
docker cp "$hermesDir\gui.py" hermes:/opt/data/gui.py
Write-Host "Files copied to container" -ForegroundColor Green

# Restart GUI
docker exec hermes pkill -f "python3 /opt/data/gui.py" 2>$null
Start-Sleep -Seconds 1
docker exec -d hermes python3 /opt/data/gui.py
Write-Host "GUI restarted" -ForegroundColor Green

Write-Host "Rollback to $Version completed!" -ForegroundColor Cyan
