#!/usr/bin/env bash
# SATeacher — one-shot setup for macOS / Linux.
# Creates venv, installs Python deps, installs Node deps, and prints next steps.
# Safe to re-run (idempotent).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "🔧 SATeacher setup"
echo "   Root: $ROOT"
echo

# --- Python ---------------------------------------------------------------
echo "📦 Python venv + dependencies"
python3 -m venv .venv
# shellcheck source=/dev/null
. .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r backend/requirements.txt

# Optional: Tesseract OCR hint
if ! command -v tesseract >/dev/null 2>&1; then
    echo "   ⚠️  tesseract not found (optional, for scanned PDF OCR)"
    case "$(uname -s)" in
        Darwin) echo "      brew install tesseract" ;;
        Linux)  echo "      sudo apt install tesseract-ocr" ;;
    esac
else
    echo "   ✅ tesseract found: $(tesseract --version 2>&1 | head -1)"
fi

# Optional: WeasyPrint system libs hint
echo "   ℹ️  PDF 导出需要系统库（WeasyPrint 依赖 pango/cairo/gdk-pixbuf/harfbuzz）"
case "$(uname -s)" in
    Darwin)
        if ! brew list pango cairo gdk-pixbuf harfbuzz >/dev/null 2>&1; then
            echo "      brew install pango cairo gdk-pixbuf harfbuzz"
        else
            echo "      ✅ WeasyPrint 系统库已安装"
        fi
        ;;
    Linux)
        if ! dpkg -l libpango-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libharfbuzz0b >/dev/null 2>&1; then
            echo "      sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libharfbuzz0b"
        else
            echo "      ✅ WeasyPrint 系统库已安装"
        fi
        ;;
esac

# Optional: macOS Vision
if [[ "$(uname -s)" == "Darwin" ]]; then
    if python3 -c "import objc" 2>/dev/null; then
        if python3 -c "import Vision" 2>/dev/null; then
            echo "   ✅ macOS Vision 可用（pyobjc-framework-Vision 已安装）"
        else
            echo "   ℹ️  macOS Vision 可选（pip install pyobjc-framework-Vision）"
        fi
    else
        echo "   ℹ️  macOS Vision 可选（先 pip install pyobjc，再 pip install pyobjc-framework-Vision）"
    fi
fi

# --- Node / frontend ------------------------------------------------------
echo
echo "📦 Frontend dependencies"
cd "$ROOT/frontend"
if [ -d node_modules ]; then
    echo "   node_modules 存在，跳过 npm install（如需重装请先删除 node_modules）"
else
    npm install
fi

# Optional: MathJax bridge
if [ -d "$ROOT/backend/app/export/mathjax" ]; then
    echo "   ℹ️  数学公式桥接（可选，需要 Node）："
    echo "      cd backend/app/export/mathjax && npm install"
    echo "      缺失时公式降级为纯文本，不影响导出"
fi

# --- .env.example ---------------------------------------------------------
echo
echo "📝 环境变量模板"
cd "$ROOT"
if [ ! -f .env ]; then
    cat > .env <<'EOF'
# SATeacher runtime configuration
# Copy or rename to .env and adjust as needed.
# SATEACHER_DATA: 数据根目录（默认 ./data）
# SATEACHER_API:  Vite 代理的后端地址（默认 http://localhost:8000）
# 也可导出到 shell 而非写文件。
# SATEACHER_DATA=/absolute/path/to/data
# SATEACHER_API=http://localhost:8000
EOF
    echo "   已创建 .env（已含注释，按需修改）"
else
    echo "   .env 已存在，跳过"
fi

# --- Done -----------------------------------------------------------------
echo
echo "✅ Setup 完成"
echo
echo "🚀 启动开发环境："
echo "   ./scripts/dev.sh"
echo
echo "   或者分别启动："
echo "   # 终端 A - 后端"
echo "   . .venv/bin/activate"
echo "   uvicorn app.main:app --app-dir backend --reload --port 8000"
echo
echo "   # 终端 B - 前端"
echo "   cd frontend && npm run dev"
echo
echo "🔗 访问：http://localhost:5173"
echo "🩺 健康检查：http://localhost:8000/api/health"