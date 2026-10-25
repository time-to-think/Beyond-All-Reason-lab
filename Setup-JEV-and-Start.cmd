@echo off
setlocal
set "BAR_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%BAR_PYTHON%" set "BAR_PYTHON=python"
"%BAR_PYTHON%" "%~dp0launcher\setup_jev.py" %*
set "BAR_EXIT=%ERRORLEVEL%"
pause
exit /b %BAR_EXIT%
