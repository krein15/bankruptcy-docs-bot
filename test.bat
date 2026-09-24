@echo off
chcp 65001 > nul
rem Прогон всех автотестов двойным щелчком. Бот при этом не запускается и в Telegram ничего не пишет.
cd /d "%~dp0"

".venv\Scripts\python.exe" -c "import pytest" 2>nul || (
    echo pytest не установлен. Установите:
    echo   .venv\Scripts\pip install -r requirements-dev.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pytest -v
pause
