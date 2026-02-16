@echo off
setlocal
REM Si tenes un dominio reservado de ngrok:
REM ngrok http --domain=tu-dominio.ngrok-free.app 8000
ngrok http 8000
