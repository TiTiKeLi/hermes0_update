# Hermes Git Sync — 每小时自动提交 + 推送
$ErrorActionPreference = "SilentlyContinue"
Set-Location "C:\Users\Lsc\.hermes"
$status = git status --short
if (-not $status) { exit 0 }
& "C:\Users\Lsc\.hermes\data-security-audit.ps1"
if ($LASTEXITCODE -ne 0) { exit 1 }
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git add -A
git commit -m "auto: $timestamp — $($status.Count) files changed"
git push origin master 2>&1 | Out-Null
