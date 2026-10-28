@echo off
chcp 65001 >nul
set "PASTA=%~dp0"
echo =====================================
echo  TRANSCRITOR DE AUDIO - Segundo Cerebro
echo  Abrindo em http://127.0.0.1:5055
echo  (feche esta janela para encerrar)
echo =====================================
rem Se uma versao antiga ainda estiver rodando na porta 5055, encerra antes de iniciar
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5055 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
cd /d "%PASTA%"
python app.py
pause
