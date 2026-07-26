 # Hermes Bridge Monitor — 极简版本
 # 只做一件事：检查bridge目录，通知 Codex
 # 没有 git、没有审计、没有多余操作
 
 $ErrorActionPreference = "SilentlyContinue"
 $reqDir = "C:\Users\Lsc\.hermes\codex-bridge\requests"
 
 $files = Get-ChildItem $reqDir\*.json -ErrorAction SilentlyContinue
 if ($files.Count -gt 0) {
     Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 发现 $($files.Count) 个新请求"
 }
