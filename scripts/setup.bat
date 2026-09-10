@echo off
rem ===== 个人 App 首次安装脚本 =====

set "CONDA_DIR=D:\ProgramData\miniconda"
set "CONDA=%CONDA_DIR%\Scripts\conda.exe"
set "PY=%CONDA_DIR%\envs\personal-app\python.exe"

if not exist "%CONDA%" (
    echo [错误] 未找到 conda：%CONDA%
    pause
    exit /b 1
)

if not exist "%PY%" (
    echo [1/3] 创建独立 conda 环境 personal-app (Python 3.13)...
    call "%CONDA%" create -n personal-app python=3.13 -y
) else (
    echo [1/3] conda 环境 personal-app 已存在，跳过创建
)

if not exist "%PY%" (
    echo [错误] 环境创建失败，请检查上方报错信息
    pause
    exit /b 1
)

echo.
echo [2/3] 安装后端依赖（清华镜像）...
"%PY%" -m pip install -r "%~dp0..\backend\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo [3/3] 安装前端依赖...
pushd "%~dp0..\frontend"
call npm install
popd

echo.
echo ==========================================
echo   安装完成！以后双击 scripts\start.bat 启动
echo ==========================================
pause
