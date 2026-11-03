@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title STILL Variant PDP

echo ========================================
echo   STILL 商品详情页 - 本地启动
echo ========================================
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有检测到 Node.js。
  echo.
  echo 请先安装 Node.js LTS 版本：
  echo   https://nodejs.org/zh-cn/download
  echo.
  echo 安装时保持默认选项，安装完成后重新双击本文件。
  echo.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有检测到 npm。请重新安装 Node.js LTS。
  pause
  exit /b 1
)

if not exist "node_modules" (
  echo [1/2] 首次运行，正在安装依赖……
  call npm install
  if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，请检查网络后重试。
    pause
    exit /b 1
  )
)

if not exist ".env" (
  echo [提示] 未找到 .env，将按同源 /api 请求后端。
  echo        如需代理到其他地址，请复制 .env.example 为 .env 并修改。
  echo.
)

echo [2/2] 正在启动 Vite 开发服务器……
echo        浏览器会自动打开；若没有打开，请访问终端里显示的地址。
echo        按 Ctrl+C 可以停止服务。
echo.

call npm run dev -- --open

echo.
echo 开发服务器已停止。
pause
