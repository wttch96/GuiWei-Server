@echo off
chcp 65001 >nul
setlocal
title GuiWei Backend

cd /d "%~dp0backend"

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 python，请先安装 Python 3.11+ 并加入 PATH。
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/2] 正在创建虚拟环境 backend\.venv ...
  python -m venv .venv
  if errorlevel 1 goto :error
  echo [2/2] 正在安装后端依赖 ...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo [提示] 已根据 .env.example 生成 backend\.env
  echo        请填写 SECRET_KEY、JWT_SECRET、DEEPSEEK_API_KEY 等配置后重启。
)

echo.
echo 后端启动中：http://127.0.0.1:5000
echo 按 Ctrl+C 停止服务。
echo.
".venv\Scripts\python.exe" run.py
goto :eof

:error
echo.
echo [错误] 后端启动失败，请查看上方日志。
pause
exit /b 1
