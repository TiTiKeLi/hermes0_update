# State Machine Helper — Codex 端状态管理

function Set-SMState {
    param(
        [string]$SMId,
        [string]$NewState,
        [string]$By = "codex",
        [hashtable]$Result = $null
    )
    $path = "C:\Users\Lsc\.hermes\codex-bridge\state-machine\$SMId.json"
    if (-not (Test-Path $path)) { Write-Host "[SM] 找不到: $SMId"; return }
    
    $sm = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
    $now = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    $sm.state = $NewState
    $sm.updated_at = $now
    $sm.history += @(@{state=$NewState; at=$now; by=$By})
    if ($Result) { $sm.result = $Result }
    $sm | ConvertTo-Json -Depth 10 | Set-Content $path -Encoding UTF8 -Force
    Write-Host "[SM] $($sm.id): $NewState"
}

function New-SM {
    param([string]$Type, [string]$Summary, [string]$Detail = "")
    $id = "sm-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $now = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    $sm = @{
        id = $id; type = $Type; state = "PENDING"
        created_by = "codex"; context = @{summary=$Summary; detail=$Detail}
        result = $null; error = $null
        history = @(@{state="PENDING"; at=$now; by="codex"})
        created_at = $now; updated_at = $now
    }
    $sm | ConvertTo-Json -Depth 10 | Out-File "C:\Users\Lsc\.hermes\codex-bridge\state-machine\$id.json" -Encoding UTF8 -Force
    Write-Host "[SM] 已创建: $id"
    return $id
}

# 导出函数
Export-ModuleMember -Function Set-SMState, New-SM
