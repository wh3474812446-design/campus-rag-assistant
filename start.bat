@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RAG 知识库（请勿关闭本窗口，关闭即停止服务）

rem === 确保本机回环不走代理（防止代理开着时连不上后端）===
set "NO_PROXY=127.0.0.1,localhost,%NO_PROXY%"
set "no_proxy=127.0.0.1,localhost,%no_proxy%"

echo ============================================
echo    RAG 知识库 启动中...
echo    (只有这一个窗口，前端会自动拉起后端)
echo    (请勿关闭本窗口，关闭即停止服务)
echo ============================================
echo.

echo [1/2] 清理可能残留的旧后端进程（占用 8000 端口会导致后端连不上）...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo     - 结束残留进程 PID %%p
    taskkill /f /pid %%p >nul 2>&1
)

rem 首次运行时跳过 streamlit 的邮箱输入提示（否则会卡住）
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

echo [2/2] 打开网页（前端会在后台自动启动后端，首次需加载向量模型，请耐心等待）...
echo.
streamlit run streamlit_app.py
