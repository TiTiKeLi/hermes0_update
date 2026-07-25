@echo off
chcp 65001 >nul
title Hermes Dashboard

echo.
echo  ========================================
echo    Hermes Dashboard
echo  ========================================
echo.

:: Start gui.py inside container if not already running
docker exec hermes sh -c "ss -tlnp 2>/dev/null | grep -q ':8644 ' && echo running || echo stopped" 2>nul | findstr /i "stopped" >nul
if %ERRORLEVEL%==0 (
    echo  Starting GUI server in container...
    docker exec -d hermes python3 /opt/data/gui.py
    timeout /t 2 /nobreak >nul
) else (
    echo  GUI server already running.
)

echo  Opening http://127.0.0.1:8644 in browser...
start http://127.0.0.1:8644

echo.
echo  Dashboard is running at: http://127.0.0.1:8644
echo  Press Ctrl+C to stop (or close this window).
echo.
pause
