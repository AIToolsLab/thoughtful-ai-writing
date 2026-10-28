@echo off
title Thoughtful AI Writing - DeepSeek Proxy
cd /d "%~dp0"

echo ============================================
echo  Thoughtful AI Writing - DeepSeek Proxy
echo ============================================
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js from https://nodejs.org and try again.
    pause
    exit /b 1
)

echo Starting DeepSeek CORS proxy...
echo Keep this window open while using the app.
echo.
echo Opening bit_meter.html in your browser...
start "" "%~dp0bit_meter.html"

echo.
echo Proxy running at http://localhost:3000
echo Press Ctrl+C to stop.
echo.
node deepseek-proxy.js

pause
