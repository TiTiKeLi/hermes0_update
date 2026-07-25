# Hermes Git Sync — 每小时自动提交 + 推送
$ErrorActionPreference = "SilentlyContinue"
Set-Location "C:\Users\Lsc\.hermes"

$status = git status --short
if (-not $status) { exit 0 }

# 安全审计：data-security-audit (文件名+内容)
& "C:\Users\Lsc\.hermes\data-security-audit.ps1"
if ($LASTEXITCODE -ne 0) { exit 1 }

# 安全审计：Gitleaks (150+模式+熵检测)
$gitleaks = "C:\Users\Lsc\AppData\Local\gitleaks\gitleaks.exe"
if (Test-Path $gitleaks) {
    & $gitleaks detect --source="C:\Users\Lsc\.hermes" --no-git 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "Gitleaks blocked" -ForegroundColor Red; exit 1 }
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git add -A
git commit -m "auto: $timestamp — $($status.Count) files changed"
git push origin master 2>&1 | Out-Null
