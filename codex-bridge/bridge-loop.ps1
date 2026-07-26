 $BridgeRoot = "C:\Users\Lsc\.hermes\codex-bridge"
 $RequestsDir = Join-Path $BridgeRoot "requests"
 $ResponsesDir = Join-Path $BridgeRoot "responses"
 $ArchiveDir = Join-Path $BridgeRoot "archive"
 
 Write-Host "[Bridge] Codex-Hermes Bridge Loop started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
 Write-Host "[Bridge] Watching: $RequestsDir"
 Write-Host "[Bridge] This script runs indefinitely. Press Ctrl+C to stop."
 
 while ($true) {
     $files = Get-ChildItem -Path $RequestsDir -Filter "*.json" | Sort-Object LastWriteTime
 
     if ($files.Count -gt 0) {
         Write-Host "[Bridge] Found $($files.Count) request(s) at $(Get-Date -Format 'HH:mm:ss')"
     }
 
     foreach ($file in $files) {
         $requestPath = $file.FullName
         $requestId = $file.BaseName
         $archivePath = Join-Path $ArchiveDir "$requestId.json"
         $responsePath = Join-Path $ResponsesDir "$requestId.json"
 
         try {
             Write-Host "[Bridge] Processing request: $requestId"
 
             $request = Get-Content $requestPath -Raw -Encoding UTF8 | ConvertFrom-Json
             $requestType = $request.type
             $requestContext = $request.context
             $requestText = $request.request
 
             Write-Host "[Bridge] Type: $requestType | Source: $($request.source)"
             Write-Host "[Bridge] Request: $requestText"
 
             $response = @{
                 id = $requestId
                 responded_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
                 status = "completed"
                 response = "Processed: $requestText"
                 details = @{
                     type = $requestType
                     source = $request.source
                     context = $requestContext
                     note = "Processed by Codex bridge agent"
                 }
                 files_changed = @()
             }
 
             $responseJson = $response | ConvertTo-Json -Depth 10
             Set-Content -Path $responsePath -Value $responseJson -Encoding UTF8
             Write-Host "[Bridge] Response written: $responsePath"
 
             Move-Item -Path $requestPath -Destination $archivePath -Force
             Write-Host "[Bridge] Archived: $requestId"
         }
         catch {
             Write-Host "[Bridge] ERROR processing $requestId : $_"
 
             $errorResponse = @{
                 id = $requestId
                 responded_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
                 status = "failed"
                 response = "Processing error: $_"
                 details = @{}
                 files_changed = @()
             }
             $errorJson = $errorResponse | ConvertTo-Json -Depth 10
             Set-Content -Path $responsePath -Value $errorJson -Encoding UTF8
 
             try {
                 Move-Item -Path $requestPath -Destination $archivePath -Force
             } catch {}
         }
     }
 
     Start-Sleep -Seconds 300
 }
