@echo off
chcp 65001 >nul
echo ====================================================
echo   智能旅行规划平台 - 后端启动
echo ====================================================
cd /d "%~dp0backend"

REM 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [初始化] 创建 Python 虚拟环境...
    python -m venv .venv
)

REM 激活虚拟环境
call ".venv\Scripts\activate.bat"

REM 安装依赖
echo [依赖] 检查并安装依赖...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet

REM 首次初始化数据库（数据库不存在时自动创建）
echo [数据库] 初始化数据库表结构与演示数据...
python -c "from app import app, db; from app import _seed_demo_data; app.app_context().__enter__(); db.create_all(); _seed_demo_data(); print('数据库就绪')" 2>nul
flask init-db

echo.
echo [启动] Flask 服务 http://127.0.0.1:5000
echo [账号] admin / 123456
echo ====================================================
python app.py
pause
