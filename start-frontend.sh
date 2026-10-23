#!/usr/bin/env bash
# 启动前端（Linux / macOS / Git Bash）
set -euo pipefail

cd "$(dirname "$0")/frontend"

if ! command -v npm >/dev/null 2>&1; then
  echo "[错误] 未找到 npm，请先安装 Node.js 18+ 并加入 PATH。" >&2
  echo "       如果使用 fnm / nvm，请先执行 fnm use 或 nvm use。" >&2
  exit 1
fi

if [ ! -d "node_modules" ]; then
  echo "正在安装前端依赖 ..."
  npm install
fi

echo
echo "前端启动中：http://localhost:5173"
echo "手机访问：http://电脑局域网IP:5173（需与电脑同一 Wi-Fi）"
echo "请确保后端已在 http://127.0.0.1:5555 运行。"
echo "按 Ctrl+C 停止服务。"
echo
exec npm run dev
