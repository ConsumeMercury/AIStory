# Shadow-mode play session — PowerShell helper for Windows.
# Usage:
#   .\scripts\shadow_play.ps1              # print env + commands
#   .\scripts\shadow_play.ps1 -Server      # set env and start web server
#   .\scripts\shadow_play.ps1 -Cli         # set env and start CLI (python src/main.py)

param(
    [switch]$Server,
    [switch]$Cli
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$env:AISTORY_PROSE_AUDITOR = "shadow"
$env:AISTORY_ACTION_CLASSIFIER = "shadow"
$env:AISTORY_DEBUG = "1"
$env:AISTORY_BOUNDARY_HISTORY = "20"

Write-Host "Shadow mode env set for this session:" -ForegroundColor Cyan
Write-Host "  AISTORY_PROSE_AUDITOR=$env:AISTORY_PROSE_AUDITOR"
Write-Host "  AISTORY_ACTION_CLASSIFIER=$env:AISTORY_ACTION_CLASSIFIER"
Write-Host "  AISTORY_DEBUG=$env:AISTORY_DEBUG"
Write-Host "  AISTORY_BOUNDARY_HISTORY=$env:AISTORY_BOUNDARY_HISTORY"
Write-Host ""
Write-Host "After playing, review metrics:" -ForegroundColor Yellow
Write-Host "  python scripts/debug_state.py boundary"
Write-Host ""

if ($Server) {
    Write-Host "Starting server..." -ForegroundColor Green
    python -m uvicorn api.server:app --host 127.0.0.1 --port 8765 --reload
    exit $LASTEXITCODE
}

if ($Cli) {
    Write-Host "Starting CLI..." -ForegroundColor Green
    python src/main.py
    exit $LASTEXITCODE
}

Write-Host "To set vars manually in PowerShell (current session only):" -ForegroundColor DarkGray
Write-Host '  $env:AISTORY_PROSE_AUDITOR = "shadow"'
Write-Host '  $env:AISTORY_ACTION_CLASSIFIER = "shadow"'
Write-Host '  $env:AISTORY_DEBUG = "1"'
Write-Host ""
Write-Host "Or add the same lines to .env (persistent — restart server after edit)." -ForegroundColor DarkGray
Write-Host ""
Write-Host "Then start the game in THIS SAME terminal:" -ForegroundColor Green
Write-Host "  python -m uvicorn api.server:app --host 127.0.0.1 --port 8765 --reload"
Write-Host "  # or: python src/main.py"
