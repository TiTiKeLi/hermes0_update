# Hermes GUI 版本备份脚本
# 用法: .\backup-version.ps1 v2.4

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    [string]$Description = ""
)

$versionsDir = "C:\Users\Lsc\.hermes\versions"
$hermesDir = "C:\Users\Lsc\.hermes"
$targetDir = "$versionsDir\$Version"

if (Test-Path $targetDir) {
    Write-Host "Warning: Version $Version already exists. Overwrite? (Y/N)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -ne "Y") {
        Write-Host "Cancelled" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Creating backup for version $Version..." -ForegroundColor Cyan

# Create directory
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

# Copy files
Copy-Item "$hermesDir\gui.html" "$targetDir\gui.html" -Force
Copy-Item "$hermesDir\gui.py" "$targetDir\gui.py" -Force

# Create version info
@"
# Version: $Version
# Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Description: $Description

## Files
- gui.html: $(Get-Item "$hermesDir\gui.html" | Select-Object -ExpandProperty Length) bytes
- gui.py: $(Get-Item "$hermesDir\gui.py" | Select-Object -ExpandProperty Length) bytes
"@ | Out-File "$targetDir\VERSION.txt"

Write-Host "Backup created: $targetDir" -ForegroundColor Green
Write-Host "Files:" -ForegroundColor Yellow
Get-ChildItem $targetDir | ForEach-Object { Write-Host "  $($_.Name) ($($_.Length) bytes)" }
