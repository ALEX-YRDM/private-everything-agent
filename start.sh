#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
if [ ! -d ".venv" ]; then
  echo "创建 Python 虚拟环境..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# 安装/更新依赖
echo "检查 Python 依赖..."
pip install -e . -q

# 检查 .env 文件
if [ ! -f ".env" ]; then
  echo "未找到 .env 文件，从 .env.example 复制..."
  cp .env.example .env
  echo "请编辑 .env 文件填入 API Key，然后重新运行 start.sh"
  exit 1
fi

# 构建前端
if [ ! -d "frontend/dist" ] || [ "$(find frontend/src -newer frontend/dist -name '*.vue' -o -name '*.ts' 2>/dev/null | head -1)" ]; then
  echo "构建前端..."
  cd frontend
  npm install -q
  npm run build
  cd ..
fi

echo ""
echo "============================================"
echo "  启动 Agent 系统"
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:8000 (生产模式)"
echo "============================================"
echo ""

# 启动后端（生产模式，静态文件由 FastAPI 服务）
uvicorn backend.main:app --host 0.0.0.0 --port 8000
