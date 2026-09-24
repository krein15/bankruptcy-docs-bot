@echo off
chcp 65001 > nul
rem Запуск бота двойным щелчком. После ошибки окно не закрывается, чтобы её можно было прочитать.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Не найдено виртуальное окружение .venv. Создайте его и установите зависимости:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo Не найден файл .env. Скопируйте .env.example в .env и впишите токен бота.
    pause
    exit /b 1
)

title Бот сбора документов
echo Бот запускается. Остановить: Ctrl+C
".venv\Scripts\python.exe" -m bot
pause
