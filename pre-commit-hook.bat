@echo off
REM Hermes Data Security Audit ? Pre-commit Hook
REM ??: copy to .git\hooks\pre-commit
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Lsc\.hermes\data-security-audit.ps1"
if %errorlevel% neq 0 exit /b %errorlevel%
