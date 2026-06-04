@echo off
chcp 65001 >nul
echo 启动后端 API (http://127.0.0.1:8000/docs) ...
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
