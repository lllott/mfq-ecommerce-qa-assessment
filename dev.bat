@echo off
rem One-command local dev: FastAPI backend + Vite frontend.
rem Real logic lives in dev.ps1; this wrapper bypasses the script policy.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*
set "EXITCODE=%ERRORLEVEL%"
if not "%~1"=="" goto :end
echo.
pause
:end
exit /b %EXITCODE%
