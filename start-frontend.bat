@echo off
chcp 65001 >nul
echo ====================================================
echo   智能旅行规划平台 - 前端启动
echo ====================================================
cd /d "%~dp0frontend"

REM 检查 node_modules
if not exist "node_modules" (
    echo [依赖] 首次启动，安装 npm 依赖（国内镜像加速）...
    call npm install --registry=https://registry.npmmirror.com
)

echo [启动] Vite 开发服务器 http://127.0.0.1:5173
echo [说明] 已配置 /api 代理到后端 5000 端口
echo ====================================================
npm run dev
pause
