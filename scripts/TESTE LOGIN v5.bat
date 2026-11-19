@echo off
chcp 65001 >nul
title Teste de login OAuth (v5)
set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0py\v5\login_test.py"
