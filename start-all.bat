@echo off
chcp 65001 >nul
echo ====================================================
echo   智能旅行规划平台 - 一键启动
echo ====================================================
echo.
echo 启动后端服务（新窗口）...
start "后端-Flask" cmd /k "%~dp0start-backend.bat"

echo 等待后端启动 5 秒...
timeout /t 5 /nobreak >nul

echo 启动前端服务（新窗口）...
start "前端-Vue" cmd /k "%~dp0start-frontend.bat"

echo.
echo ====================================================
echo   两个窗口已启动：
echo   - 后端 http://127.0.0.1:5000
echo   - 前端 http://127.0.0.1:5173
echo   演示账号 admin / 123456
echo ====================================================
echo.
echo 本窗口可关闭，保留后端 / 前端窗口即可。
pause
