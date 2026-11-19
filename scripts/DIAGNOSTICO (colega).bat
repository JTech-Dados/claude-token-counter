@echo off
chcp 65001 >nul
title Diagnostico - Contador de Tokens (colega)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0diag_colega.ps1" > "%~dp0diag_colega.txt" 2>&1
echo(
type "%~dp0diag_colega.txt"
echo(
echo ------------------------------------------------------------
echo Arquivo salvo: %~dp0diag_colega.txt
echo Ele NAO contem o token — pode enviar sem problema.
echo ------------------------------------------------------------
pause
