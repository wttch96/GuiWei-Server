@echo off
chcp 65001 >nul
setlocal
title GuiWei Frontend

cd /d "%~dp0frontend"

where npm >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 npm，请先安装 Node.js 18+ 并加入 PATH。
  echo        如果使用 fnm / nvm，请先在终端执行 fnm use 或 nvm use。
  pause
  exit /b 1
)

if not exist "node_modules" (
  echo 正在安装前端依赖 ...
  call npm install
  if errorlevel 1 goto :error
)

echo.
echo 前端启动中：http://localhost:5173
echo 手机访问：http://电脑局域网IP:5173（需与电脑同一 Wi-Fi）
echo 请确保后端已在 http://127.0.0.1:5000 运行。
echo 按 Ctrl+C 停止服务。
echo.
call npm run dev
goto :eof

:error
echo.
echo [错误] 前端启动失败，请查看上方日志。
pause
exit /b 1
