@echo off
chcp 65001 >nul
title AI TradeBot

echo ========================================
echo    AI TradeBot 量化交易系统
echo ========================================

cd /d "%~dp0"

echo [1/3] 检查Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python
    pause
    exit /b 1
)

echo [2/3] 检查Node.js...
node --version >nul 2>&1

echo [3/3] 启动服务...

echo.
echo 启动后端 (端口 8000)...
start "Backend" cmd /k "cd /d %~dp0backend && python main.py"

timeout /t 2 /nobreak >nul

echo 启动前端 (端口 5173)...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo 启动完成！
echo 前端: http://localhost:5173
echo 后端: http://localhost:8000
echo ========================================
pause
