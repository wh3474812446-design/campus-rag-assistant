@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 校园知识库问答助手 - 一键安装

echo ============================================================
echo            校园知识库问答助手   一键安装向导
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

echo [3/3] 配置 DeepSeek API Key...
if not exist ".env" copy ".env.example" ".env" >nul
echo.
echo   请先到  https://platform.deepseek.com  注册，并在「API Keys」里新建一个 key。
echo   （key 形如 sk-xxxxxxxxxxxxxxxx）
echo.
set /p APIKEY="   把你的 key 粘贴到这里后按回车（直接回车=稍后手动填）: "
if not "%APIKEY%"=="" (
    powershell -NoProfile -Command "$c=[IO.File]::ReadAllText('.env'); $c=[Regex]::Replace($c,'(?m)^DEEPSEEK_API_KEY=.*$','DEEPSEEK_API_KEY=%APIKEY%'); [IO.File]::WriteAllText('.env',$c,(New-Object Text.UTF8Encoding $false))"
    echo   [OK] 已写入 .env。
) else (
    echo   [!] 已跳过。请稍后用记事本打开 .env 文件，
    echo       把 DEEPSEEK_API_KEY= 后面改成你自己的 key 再保存。
)
echo.

echo ============================================================
echo   安装完成！以后每次使用，只需双击  start.bat  即可。
echo ============================================================
echo.
set /p RUNNOW="   现在就启动试试吗？(Y / N): "
if /i "%RUNNOW%"=="Y" (
    start "" "%~dp0start.bat"
    exit /b 0
)
echo.
pause
