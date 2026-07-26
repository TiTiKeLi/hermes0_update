# Hermes Codex Bridge — 发送请求给 Codex
$ErrorActionPreference = "SilentlyContinue"
$bridgeDir = "$env:USERPROFILE\.hermes\codex-bridge"
$reqDir = "$bridgeDir\requests"
$resDir = "$bridgeDir\responses"

# 检查是否有待处理的响应
$responses = Get-ChildItem $resDir\*.json -ErrorAction SilentlyContinue
foreach ($r in $responses) {
    $content = Get-Content $r.FullName -Raw | ConvertFrom-Json
    Write-Host "Codex 响应 [$($r.BaseName)]: $($content.response)"
    # 归档
    Move-Item $r.FullName "$bridgeDir\archive\$($r.Name)" -Force
}

# 创建新请求
function Send-CodexRequest {
    param($Type, $Context, $Request)
    $id = "req-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$(Get-Random -Max 999)"
    $body = @{
        id = $id
        created_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
        source = "hermes-cron"
        type = $Type
        context = $Context
        request = $Request
    } | ConvertTo-Json
    $body | Out-File "$reqDir\$id.json" -Encoding utf8 -Force
    Write-Host "请求已发送: $id ($Type)"
    return $id
}
