@echo off
chcp 65001 >nul
title Diagnostico - Contador de Tokens
set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0py\diag_v4.py" > "%~dp0diag_v4.txt" 2>&1
echo Diagnostico salvo em: %~dp0diag_v4.txt
echo(
type "%~dp0diag_v4.txt"
echo(
pause
