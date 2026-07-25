@echo off
REM Hermes Data Security Audit ? Pre-commit Hook
REM ??: copy to .git\hooks\pre-commit
REM ?????????????

REM Layer 1: data-security-audit (22???? + ??????)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Lsc\.hermes\data-security-audit.ps1"
if %%errorlevel%% neq 0 exit /b %%errorlevel%%

REM Layer 2: Gitleaks (150+?? + ???)
"C:\Users\Lsc\AppData\Local\gitleaks\gitleaks.exe" detect --source="C:\Users\Lsc\.hermes" --no-git
if %%errorlevel%% neq 0 exit /b %%errorlevel%%
