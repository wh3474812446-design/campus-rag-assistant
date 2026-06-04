@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 校园知识库问答助手
echo ============================================
echo    校园知识库问答助手 启动中...
echo    (这个窗口请勿关闭，关闭即停止服务)
echo ============================================
echo.

echo [1/3] 启动后端服务...
start "校园助手-后端服务(勿关)" cmd /k uvicorn app.main:app --host 127.0.0.1 --port 8000

echo [2/3] 等待后端就绪（首次启动需加载向量模型，请耐心等待）...
:waitloop
ping -n 2 127.0.0.1 >nul
curl -s http://127.0.0.1:8000/api/health >nul 2>&1
if errorlevel 1 goto waitloop

echo [3/3] 后端已就绪，正在打开网页...
echo.
streamlit run streamlit_app.py
