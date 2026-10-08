<#
.SYNOPSIS
    SATeacher — one-shot setup for Windows (PowerShell).
    Creates venv, installs Python deps, installs Node deps, and prints next steps.
    Safe to re-run (idempotent).

.DESCRIPTION
    This script sets up the SATeacher development environment on Windows.
    It creates a Python virtual environment, installs backend dependencies,
    installs frontend Node.js dependencies, and creates an .env file template.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ROOT = Split-Path -Parent $ROOT
Set-Location $ROOT

Write-Host "🔧 SATeacher setup" -ForegroundColor Cyan
Write-Host "   Root: $ROOT"
Write-Host ""

# --- Python ---------------------------------------------------------------
Write-Host "📦 Python venv + dependencies" -ForegroundColor Green

if (-not (Test-Path ".venv")) {
    Write-Host "   Creating virtual environment..."
    python -m venv .venv
} else {
    Write-Host "   Virtual environment already exists."
}

. .venv\Scripts\Activate.ps1
Write-Host "   Upgrading pip..."
python -m pip install --upgrade pip 2>$null | Out-Null
Write-Host "   Installing backend requirements..."
pip install -r backend\requirements.txt

# Optional: Tesseract OCR hint
if (-not (Get-Command tesseract -ErrorAction SilentlyContinue)) {
    Write-Host "   ⚠️  tesseract not found (optional, for scanned PDF OCR)" -ForegroundColor Yellow
    Write-Host "      choco install tesseract" -ForegroundColor Gray
    Write-Host "      或从 https://github.com/UB-Mannheim/tesseract/wiki 下载安装" -ForegroundColor Gray
} else {
    $ver = tesseract --version 2>&1 | Select-Object -First 1
    Write-Host "   ✅ tesseract found: $ver" -ForegroundColor Green
}

# Optional: WeasyPrint system libs hint (GTK on Windows)
Write-Host "   ℹ️  PDF 导出需要系统库（WeasyPrint 依赖 GTK3 / pango / cairo / gdk-pixbuf / harfbuzz）" -ForegroundColor Cyan
Write-Host "      推荐：choco install gtk3" -ForegroundColor Gray
Write-Host "      或按 https://weasyprint.readthedocs.io/en/stable/install.html#windows 操作" -ForegroundColor Gray

# --- Node / frontend ------------------------------------------------------
Write-Host ""
Write-Host "📦 Frontend dependencies" -ForegroundColor Green
Set-Location "$ROOT\frontend"

if (Test-Path "node_modules") {
    Write-Host "   node_modules 存在，跳过 npm install（如需重装请先删除 node_modules）" -ForegroundColor Yellow
} else {
    Write-Host "   Running npm install..."
    npm install
}

# Optional: MathJax bridge
if (Test-Path "$ROOT\backend\app\export\mathjax") {
    Write-Host "   ℹ️  数学公式桥接（可选，需要 Node）：" -ForegroundColor Cyan
    Write-Host "      cd backend\app\export\mathjax && npm install" -ForegroundColor Gray
    Write-Host "      缺失时公式降级为纯文本，不影响导出" -ForegroundColor Gray
}

# --- .env.example ---------------------------------------------------------
Write-Host ""
Write-Host "📝 环境变量模板" -ForegroundColor Green
Set-Location $ROOT

if (-not (Test-Path ".env")) {
    @"
# SATeacher runtime configuration
# Copy or rename to .env and adjust as needed.
# SATEACHER_DATA: 数据根目录（默认 ./data）
# SATEACHER_API:  Vite 代理的后端地址（默认 http://localhost:8000）
# 也可导出到 shell 而非写文件。
# SATEACHER_DATA=C:\path\to\data
# SATEACHER_API=http://localhost:8000
"@ | Set-Content -Path ".env" -Encoding UTF8
    Write-Host "   已创建 .env（已含注释，按需修改）" -ForegroundColor Green
} else {
    Write-Host "   .env 已存在，跳过" -ForegroundColor Yellow
}

# --- Done -----------------------------------------------------------------
Write-Host ""
Write-Host "✅ Setup 完成" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 启动开发环境：" -ForegroundColor Cyan
Write-Host "   .\scripts\dev.ps1"
Write-Host ""
Write-Host "   或者分别启动：" -ForegroundColor Gray
Write-Host "   # 终端 A - 后端" -ForegroundColor Gray
Write-Host "   . .venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "   uvicorn app.main:app --app-dir backend --reload --port 8000" -ForegroundColor Gray
Write-Host ""
Write-Host "   # 终端 B - 前端" -ForegroundColor Gray
Write-Host "   cd frontend && npm run dev" -ForegroundColor Gray
Write-Host ""
Write-Host "🔗 访问：http://localhost:5173" -ForegroundColor Cyan
Write-Host "🩺 健康检查：http://localhost:8000/api/health" -ForegroundColor Cyan