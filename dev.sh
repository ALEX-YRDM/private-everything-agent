#!/bin/bash
# 开发模式启动：后端热重载 + 前端 HMR
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查虚拟环境
if [ ! -d ".venv" ]; then
  echo "未找到 .venv，请先运行 ./start.sh 初始化环境"
  exit 1
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "⚠️  已从 .env.example 创建 .env，请填入 API Key 后重新运行"
  exit 1
fi

echo "启动开发模式..."
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:5173"
echo ""

# 在后台启动后端
source .venv/bin/activate
uvicorn backend.main:app --reload --reload-dir backend --port 8000 &
BACKEND_PID=$!

# 等待后端启动
sleep 2

# 在前台启动前端（Ctrl+C 会同时停止）
cd frontend
npm run dev &
FRONTEND_PID=$!

# 等待任意进程退出
wait $BACKEND_PID $FRONTEND_PID

# 清理
kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
