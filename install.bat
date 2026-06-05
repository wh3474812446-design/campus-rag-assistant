@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RAG 知识库 - 一键安装

echo ============================================================
echo               RAG 知识库   一键安装向导
echo ============================================================
echo.

echo [1/3] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [X] 没有检测到 Python！
    echo   请先到 https://www.python.org/downloads/ 下载安装 Python 3.10 或更高版本，
    echo   安装时务必勾选 "Add Python to PATH"，装完后重新双击本程序。
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('python --version') do echo   [OK] 已检测到 %%v
echo.

echo [2/3] 安装项目依赖（首次较慢，需下载约几百 MB，请耐心等待）...
echo.
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo   [X] 依赖安装失败，请检查网络后重试。
    echo.
    pause
    exit /b 1
)
echo.
echo   [OK] 依赖安装完成。
echo.

echo [3/3] 创建配置与桌面快捷方式...
if not exist ".env" copy ".env.example" ".env" >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
echo.

echo ============================================================
echo   安装完成！
echo   桌面已生成「RAG 知识库」图标，以后双击它即可打开网站。
echo   打开网站后，在右上角「API 设置」里填入你的 DeepSeek API Key
echo   （在 https://platform.deepseek.com 注册获取）即可开始使用。
echo ============================================================
echo.
set /p RUNNOW="   现在就启动试试吗？(Y / N): "
if /i "%RUNNOW%"=="Y" (
    start "" "%~dp0start.bat"
    exit /b 0
)
echo.
pause
