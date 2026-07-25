# Start Hermes Agent with Docker
Write-Host "Starting Hermes Agent..." -ForegroundColor Cyan

# Check if Docker is running
docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if Ollama is running
$ollamaCheck = netstat -ano | Select-String ":11434"
if (-not $ollamaCheck) {
    Write-Host "Warning: Ollama (port 11434) not detected. Please start Ollama first." -ForegroundColor Yellow
}

# Build the image if not exists
$imageExists = docker images -q hermes-agent:latest
if (-not $imageExists) {
    Write-Host "Building Hermes Docker image..." -ForegroundColor Yellow
    docker build -t hermes-agent:latest $PSScriptRoot
}

# Stop existing container
docker rm -f hermes 2>$null

# Start Hermes
Write-Host "Starting Hermes container..." -ForegroundColor Green
docker run -d `
    --name hermes `
    --restart unless-stopped `
    -p 8642:8642 `
    -v "${env:USERPROFILE}\.hermes:/opt/data" `
    -e FAL_KEY="${env:FAL_KEY}" `
    -e HERMES_AUTH_TOKEN="hermes-dev" `
    --add-host host.docker.internal:host-gateway `
    hermes-agent:latest gateway run

if ($LASTEXITCODE -eq 0) {
    Write-Host "Hermes Agent started! Gateway: http://localhost:8642" -ForegroundColor Green
    Write-Host "Check logs: docker logs hermes -f" -ForegroundColor Gray
} else {
    Write-Host "Failed to start Hermes container" -ForegroundColor Red
}
