#!/usr/bin/env bash
# 启动后端（Linux / macOS / Git Bash）
set -euo pipefail

cd "$(dirname "$0")/backend"

if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo "[错误] 未找到 python3 / python，请先安装 Python 3.11+。" >&2
  exit 1
fi

if [ -x ".venv/bin/python" ]; then
  VENV_PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  VENV_PY=".venv/Scripts/python.exe"
else
  echo "[1/2] 正在创建虚拟环境 backend/.venv ..."
  "$PY" -m venv .venv
  if [ -x ".venv/bin/python" ]; then
    VENV_PY=".venv/bin/python"
  else
    VENV_PY=".venv/Scripts/python.exe"
  fi
  echo "[2/2] 正在安装后端依赖 ..."
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "[提示] 已根据 .env.example 生成 backend/.env"
  echo "       请填写 SECRET_KEY、JWT_SECRET、DEEPSEEK_API_KEY 等配置后重启。"
fi

echo
echo "后端启动中：http://127.0.0.1:5000"
echo "手机请访问前端：http://电脑局域网IP:5173（需与电脑同一 Wi-Fi）"
echo "按 Ctrl+C 停止服务。"
echo
exec "$VENV_PY" run.py
