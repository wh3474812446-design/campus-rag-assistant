@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RAG 知识库（前端窗口）

rem === 确保本机回环不走代理（防止代理开着时连不上后端）===
set "NO_PROXY=127.0.0.1,localhost,%NO_PROXY%"
set "no_proxy=127.0.0.1,localhost,%no_proxy%"

echo ============================================
echo    RAG 知识库 启动中...
echo    (这个是前端窗口，请勿关闭，关闭即停止服务)
echo ============================================
echo.

echo [1/4] 清理可能残留的旧后端进程（占用 8000 端口会导致后端打不开）...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo     - 结束残留进程 PID %%p
    taskkill /f /pid %%p >nul 2>&1
)

echo [2/4] 启动后端服务...
start "RAG 知识库-后端服务(勿关)" cmd /k uvicorn app.main:app --host 127.0.0.1 --port 8000

echo [3/4] 等待后端就绪（首次启动需加载向量模型，请耐心等待）...
set /a _tries=0
:waitloop
ping -n 2 127.0.0.1 >nul
curl -s http://127.0.0.1:8000/api/health >nul 2>&1
if not errorlevel 1 goto ready
set /a _tries+=1
if %_tries% geq 60 goto failed
goto waitloop

:failed
echo.
echo   [X] 等待 2 分钟后端仍未就绪。
echo       请切到标题为「RAG 知识库-后端服务(勿关)」的那个黑窗口，
echo       看最后几行红色/英文报错，把它截图发给我。常见原因：
echo       - 端口 8000 仍被占用     - 依赖缺失（先跑 install.bat）
echo.
pause
exit /b 1

:ready
echo [4/4] 后端已就绪，正在打开网页...
echo.

rem 首次运行时跳过 streamlit 的邮箱输入提示（否则会卡住）
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

streamlit run streamlit_app.py
