<#
.SYNOPSIS
  Hermes 容器网络一键修复工具
.DESCRIPTION
  诊断和修复 Docker/WSL2 网络问题。
  容器采用直连 + DNS 兜底方案，不使用 host_proxy 桥接。
.PARAMETER Force
  跳过确认，直接执行全部修复步骤。
.PARAMETER CheckOnly
  仅检查网络状态，不执行修复。
#>

param(
  [switch]$Force,
  [switch]$CheckOnly
)

$ErrorActionPreference = "Continue"
$logFile = "$PSScriptRoot\logs\network-repair.log"
$null = New-Item -ItemType Directory -Path "$PSScriptRoot\logs" -Force
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Log($msg) { "$ts $msg" | Out-File -FilePath $logFile -Append -Encoding utf8; Write-Host "  $msg" }
function Ok($m)  { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "  [!] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "  [X] $m" -ForegroundColor Red }
function Section($t){ Write-Host "`n--- $t ---" -ForegroundColor Cyan }

# 1/4: Docker 环境
Section "1/4  Docker 环境"

$info = docker ps --filter name=hermes --format "{{.Status}}" 2>$null | Out-String
if ($LASTEXITCODE -ne 0) {
  $proc = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
  if (-not $proc) {
    Warn "Docker Desktop 未运行"
    if (-not $CheckOnly) {
      Log "启动 Docker Desktop..."
      Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
      Start-Sleep -Seconds 20
    }
  } else { Warn "Docker 权限不足，请以管理员身份运行" }
  if ($CheckOnly) { return }
}
if ($info -match "^Up") { Ok "Hermes 状态: $info" }
elseif ($info -match "^Exited") { Warn "Hermes 已停止" }
else { Warn "未找到 Hermes 容器" }

# 2/4: WSL2 网络重置
Section "2/4  WSL2 网络重置"
try {
  $wslOk = wsl -l -q 2>$null | Select-String -Pattern "docker-desktop|Ubuntu"
  if ($wslOk -and -not $CheckOnly) {
    wsl -d docker-desktop -u root -e sh -c "ip link set eth0 down; ip link set eth0 up" 2>$null
    Start-Sleep -Seconds 2
    Ok "WSL2 网络栈已重置"
  } elseif ($wslOk) { Ok "WSL2 运行中" }
  else { Warn "WSL2 未运行（正常）" }
} catch { Warn "WSL2 重置失败（非关键）: $_" }

# 3/4: DNS 连通性
Section "3/4  DNS 连通性"

# daemon.json 兜底
$dnsCfg = "$env:USERPROFILE\.docker\daemon.json"
if (-not (Test-Path $dnsCfg) -and -not $CheckOnly) {
  @{dns=@("8.8.8.8","223.5.5.5");"dns-opts"=@("attempts:3","timeout:2")} |
    ConvertTo-Json -Compress | Out-File $dnsCfg -Encoding utf8 -Force 2>$null
  Ok "DNS 配置已创建"
}

$dnsOk = $true
foreach ($h in @("api.openai.com","api.deepseek.com","www.baidu.com","api.github.com")) {
  $r = docker exec hermes sh -c "getent hosts $h 2>/dev/null | head -1" 2>$null
  if ($LASTEXITCODE -eq 0 -and $r) { Ok "$h → $($r -split '\s+')[0]" }
  else { Warn "$h 解析失败"; $dnsOk = $false }
}

# 4/4: 连通性测试
Section "4/4  连通性测试"

$urls = @(
  @{url="https://www.baidu.com"; tag="百度"}
  @{url="https://api.deepseek.com"; tag="DeepSeek"}
  @{url="https://api.openai.com"; tag="OpenAI"}
  @{url="https://api.github.com"; tag="GitHub"}
)
foreach ($t in $urls) {
  $r = docker exec hermes sh -c "timeout 8 curl -s -o /dev/null -w '%{http_code}|%{time_total}' --connect-timeout 5 '$($t.url)'" 2>$null
  if ($r -and $r -ne 'FAIL') {
    $p = $r -split '\|'
    Ok "$($t.tag): HTTP $($p[0]) ($($p[1])s)"
  } else { Fail "$($t.tag): 无法访问" }
}

# 修复（仅 -Force 时）
if (-not $dnsOk -and $Force) {
  Section "修复: 重启容器"
  docker compose -f "$PSScriptRoot\docker-compose.yml" down 2>$null
  Start-Sleep -Seconds 3
  docker compose -f "$PSScriptRoot\docker-compose.yml" up -d 2>$null
  if ($LASTEXITCODE -eq 0) { Ok "容器已重启" }
  else { Fail "重启失败，手动执行: docker compose up -d" }
  Start-Sleep -Seconds 5
}

Write-Host "`n[完成] 日志: $logFile" -ForegroundColor Cyan
