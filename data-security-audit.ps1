 <#
 .SYNOPSIS
   Hermes 数据安全审计 + Git pre-commit 守卫
 .DESCRIPTION
   功能 1: 扫描所有 staged 文件，阻止任何包含敏感数据的 commit。
   功能 2: 全量审计，检查工作目录中是否有不安全文件。
   在 git commit 之前自动触发，100% 拦截违规文件。
 .PARAMETER Fix
   自动将发现的违规文件移入 backups/ 或 incoming/
 .PARAMETER FullScan
   全量扫描工作目录（不只是 staged 文件）
 .EXAMPLE
   ./data-security-audit.ps1                   # 只检查 staged 文件（commit 前用）
   ./data-security-audit.ps1 -FullScan          # 全量检查工作目录
   ./data-security-audit.ps1 -Fix               # 检查并自动整理
#>

 param(
     [switch]$Fix,
     [switch]$FullScan
 )

 $ErrorActionPreference = "Continue"
 $blocked = $false

 # ========== 规则定义 ==========
 
 $blockRules = @(
     # 文件名匹配规则
     @{Pattern='\.db$'; Category='数据库'; Action='阻止'; Reason='SQLite 数据库文件包含运行时数据'},
     @{Pattern='\.db-wal$'; Category='数据库'; Action='阻止'; Reason='SQLite WAL 日志'},
     @{Pattern='\.db-shm$'; Category='数据库'; Action='阻止'; Reason='SQLite 共享内存'},
     @{Pattern='\.sqlite$'; Category='数据库'; Action='阻止'; Reason='SQLite 数据库'},
     @{Pattern='\.sqlite3$'; Category='数据库'; Action='阻止'; Reason='SQLite 数据库'},
     @{Pattern='\.log$'; Category='日志'; Action='阻止'; Reason='运行时日志'},
     @{Pattern='\.jsonl$'; Category='日志'; Action='阻止'; Reason='JSONL 日志数据'},
     @{Pattern='^session_.*\.json$'; Category='会话数据'; Action='阻止'; Reason='对话记录'},
     @{Pattern='^request_dump_.*\.json$'; Category='请求转储'; Action='阻止'; Reason='HTTP 请求内容'},
     @{Pattern='\.bak$'; Category='备份'; Action='阻止'; Reason='备份文件，无版本价值'},
     @{Pattern='\.zip$'; Category='压缩包'; Action='阻止'; Reason='大型压缩文件'},
     @{Pattern='\.tar\.gz$'; Category='压缩包'; Action='阻止'; Reason='大型压缩文件'},
     @{Pattern='\.tar$'; Category='压缩包'; Action='阻止'; Reason='大型压缩文件'},
     @{Pattern='\.mp3$'; Category='音频'; Action='阻止'; Reason='音频文件'},
     @{Pattern='\.wav$'; Category='音频'; Action='阻止'; Reason='音频文件'},
     @{Pattern='\.pyc$'; Category='编译缓存'; Action='阻止'; Reason='Python 编译字节码'},
     @{Pattern='^\.env$'; Category='密钥'; Action='阻止'; Reason='环境变量（含 API keys）'},
     @{Pattern='^auth\.json$'; Category='密钥'; Action='阻止'; Reason='认证令牌'},
     @{Pattern='^wechat_qr\.(json|png)$'; Category='密钥'; Action='阻止'; Reason='微信二维码凭证'},
     @{Pattern='^config\.yaml\.bak$'; Category='备份'; Action='阻止'; Reason='配置备份'},
     @{Pattern='^docker-compose\.yml\.bak$'; Category='备份'; Action='阻止'; Reason='配置备份'},
     @{Pattern='tirith$'; Category='二进制'; Action='阻止'; Reason='大型二进制文件'},
     @{Pattern='crewAI\.zip$'; Category='压缩包'; Action='阻止'; Reason='大型压缩文件'},
     @{Pattern='superpowers-zh\.zip$'; Category='压缩包'; Action='阻止'; Reason='大型压缩文件'},
     @{Pattern='__pycache__'; Category='编译缓存'; Action='阻止'; Reason='Python 缓存目录'}
 )
 
 $contentRules = @(
     # 文件内容匹配规则
     @{Pattern='api_key\s*:\s*''[^'']+'''; Category='密钥泄露'; Action='阻止'; Reason='config.yaml 中包含非空 API key'},
     @{Pattern='api_key\s*:\s*"[^"]+"'; Category='密钥泄露'; Action='阻止'; Reason='config.yaml 中包含非空 API key'},
     @{Pattern='password\s*[:=]\s*''[^'']+'''; Category='密钥泄露'; Action='阻止'; Reason='明文密码'},
     @{Pattern='token\s*[:=]\s*''[^'']+'''; Category='密钥泄露'; Action='阻止'; Reason='明文令牌'}
 )
 
 $sizeLimit = 1MB  # 单文件超过 1MB 警告
 
 # ========== 收集待检查文件 ==========
 
 if ($FullScan) {
     $files = Get-ChildItem -File | Select-Object FullName, Name, Length
     Write-Host "安全审计：全量扫描 ($($files.Count) 个文件)" -ForegroundColor Cyan
 } else {
     # 只检查 staged 文件（pre-commit 模式）
     $staged = git diff --cached --name-only 2>$null
     if (-not $staged) {
         Write-Host "安全审计：无 staged 文件 ✅" -ForegroundColor Green
         exit 0
     }
     $files = $staged | ForEach-Object {
         if (Test-Path $_) {
             $item = Get-Item $_
             [PSCustomObject]@{FullName=$item.FullName; Name=$item.Name; Length=$item.Length}
         }
     }
     Write-Host "安全审计：检查 $($files.Count) 个 staged 文件" -ForegroundColor Cyan
 }
 
 # ========== 执行检查 ==========
 
 $violations = @()
 
 foreach ($f in $files) {
     $fileName = $f.Name
     $fullPath = $f.FullName
     $fileSize = $f.Length
     $relativePath = $fullPath -replace [regex]::Escape("$env:USERPROFILE\.hermes\"), ''
     
     # 规则 1: 文件名匹配
     foreach ($rule in $blockRules) {
         if ($fileName -match $rule.Pattern) {
             $violations += [PSCustomObject]@{
                 File = $relativePath
                 Rule = $rule.Category
                 Reason = $rule.Reason
                 Action = $rule.Action
             }
             break
         }
     }
     
     # 规则 2: 文件内容（只检查文本文件）
     if ($fullPath -match '\.(yaml|yml|json|env|md|py|sh|ps1|txt|cfg)$') {
         $content = Get-Content $fullPath -Raw -ErrorAction SilentlyContinue
         if ($content) {
             foreach ($rule in $contentRules) {
                 if ($content -match $rule.Pattern) {
                     $violations += [PSCustomObject]@{
                         File = $relativePath
                         Rule = $rule.Category
                         Reason = $rule.Reason
                         Action = $rule.Action
                     }
                     break
                 }
             }
         }
     }
     
     # 规则 3: 文件大小
     if ($fileSize -gt $sizeLimit -and -not $FullScan) {
         # 在 commit 中，大文件可能不小心被 add
         $violations += [PSCustomObject]@{
             File = $relativePath
             Rule = '大文件'
             Reason = "超过 ${sizeLimit}MB ($('{0:N1}MB' -f ($fileSize/1MB)))"
             Action = '警告'
         }
     }
 }
 
 # ========== 输出结果 ==========
 
 if ($violations.Count -gt 0) {
     Write-Host "`n⚠️  安全审计发现问题：" -ForegroundColor Yellow
     $violations | Group-Object Action | ForEach-Object {
         $action = $_.Name
         Write-Host "`n[$action] $($_.Count) 个文件：" -ForegroundColor $(
             if ($action -eq '阻止') { 'Red' } else { 'Yellow' }
         )
         $_.Group | Format-Table File, Rule, Reason -AutoSize
     }
     
     $blockedCount = ($violations | Where-Object Action -eq '阻止' | Measure-Object).Count
     if ($blockedCount -gt 0 -and -not $FullScan) {
         Write-Host "`n❌  commit 被阻止：$blockedCount 个文件违规，原因见上表" -ForegroundColor Red
         Write-Host "   如果确实需要提交这些文件，先确认无敏感数据，然后:" -ForegroundColor Gray
         Write-Host "   git commit --no-verify -m 'message'" -ForegroundColor Gray
         exit 1
     }
     
     if ($Fix) {
         Write-Host "`n正在自动整理违规文件..." -ForegroundColor Cyan
         foreach ($v in $violations) {
             $src = "$env:USERPROFILE\.hermes\$($v.File)"
             if ($v.Rule -in @('请求转储','会话数据','日志')) {
                 $dst = "$env:USERPROFILE\.hermes\incoming\"
             } elseif ($v.Rule -eq '备份') {
                 $dst = "$env:USERPROFILE\.hermes\backups\"
             } else {
                 $dst = "$env:USERPROFILE\.hermes\cache\"
             }
             if (Test-Path $src) {
                 $null = New-Item -ItemType Directory -Path $dst -Force
                 Move-Item $src $dst -Force -ErrorAction SilentlyContinue
                 Write-Host "  已移动 $($v.File) → $dst" -ForegroundColor Gray
             }
         }
     }
 } else {
     Write-Host "`n安全审计：全部通过 ✅" -ForegroundColor Green
 }

