<#
.SYNOPSIS
    Start SATeacher backend (8000) and frontend (5173) together on Windows.
    Ctrl-C stops both.

.DESCRIPTION
    This script starts both the FastAPI backend and Vite frontend dev servers.
    It assumes the setup script has already been run (venv exists, deps installed).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ROOT = Split-Path -Parent $ROOT
Set-Location $ROOT

Write-Host "🚀 Starting SATeacher dev servers..." -ForegroundColor Cyan

# Activate venv
. .venv\Scripts\Activate.ps1

# Start backend in background
Write-Host "   Starting backend on :8000..." -ForegroundColor Green
$backend = Start-Process pwsh -ArgumentList "-NoExit", "-Command", "uvicorn app.main:app --app-dir backend --reload --port 8000" -PassThru

# Give backend a moment to start
Start-Sleep -Seconds 2

# Start frontend (blocking)
Write-Host "   Starting frontend on :5173..." -ForegroundColor Green
Set-Location "$ROOT\frontend"
try {
    npm run dev
}
finally {
    Write-Host "   Stopping backend (PID $($backend.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}