@echo off
rem ===== 个人 App 启动脚本 =====
rem 使用 Windows Terminal 单窗口左右分屏（左=后端，右=前端）；未安装 WT 时回退为两个独立窗口

set "CONDA_DIR=D:\ProgramData\miniconda"
set "PY=%CONDA_DIR%\envs\personal-app\python.exe"
set "BACKEND=%~dp0..\backend"
set "FRONTEND=%~dp0..\frontend"

if not exist "%PY%" (
    echo [错误] 未找到 conda 环境中的 Python：
    echo   %PY%
    echo 请先运行 scripts\setup.bat 完成安装
    pause
    exit /b 1
)

echo 启动后端 FastAPI（端口 8000）与前端 Vite（端口 5173）...

where wt >nul 2>nul
if %errorlevel%==0 (
    rem Windows Terminal：一个窗口左右分屏
    wt -w 0 nt -d "%BACKEND%" cmd /k %PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload ; split-pane -V -d "%FRONTEND%" cmd /k npm run dev
) else (
    rem 未安装 Windows Terminal：回退为两个独立窗口
    start "个人App-后端" /D "%BACKEND%" cmd /k %PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
    start "个人App-前端" /D "%FRONTEND%" cmd /k npm run dev
)

echo 3 秒后自动打开浏览器...
timeout /t 3 >nul
start http://localhost:5173

rem 本窗口自动关闭；停止服务请在服务窗口按 Ctrl+C 或直接关闭窗口
exit /b 0
