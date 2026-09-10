@echo off
rem ===== 个人 App 启动脚本 =====

set "CONDA_DIR=D:\ProgramData\miniconda"
set "PY=%CONDA_DIR%\envs\personal-app\python.exe"

if not exist "%PY%" (
    echo [错误] 未找到 conda 环境的 Python：
    echo   %PY%
    echo 请先运行 scripts\setup.bat 完成安装
    pause
    exit /b 1
)

echo 启动后端 FastAPI (端口 8000)...
start "个人App-后端" /D "%~dp0..\backend" cmd /k %PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

echo 启动前端 Vite (端口 5173)...
start "个人App-前端" /D "%~dp0..\frontend" cmd /k npm run dev

echo 3 秒后打开浏览器...
timeout /t 3 >nul
start http://localhost:5173

echo.
echo 已启动！关闭弹出的两个命令行窗口即可停止服务。
pause
