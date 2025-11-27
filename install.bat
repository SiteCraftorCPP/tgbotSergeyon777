@echo off
chcp 65001 >nul
cls

echo ╔════════════════════════════════════════════════════════════╗
echo ║        Установка Telegram Бота для Знакомств              ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Проверка Python
echo [1/4] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден!
    echo.
    echo Установите Python 3.8 или выше:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python %PYTHON_VERSION% найден
echo.

REM Установка зависимостей
echo [2/4] Установка зависимостей...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Ошибка при установке зависимостей
    pause
    exit /b 1
)
echo ✅ Зависимости установлены
echo.

REM Создание .env файла
echo [3/4] Настройка конфигурации...
if not exist .env (
    echo BOT_TOKEN=7682201960:AAEAS4510i6bOR3wq0taMdaq--SqnqRiR9U > .env
    echo ADMIN_ID=YOUR_TELEGRAM_ID >> .env
    echo ✅ Файл .env создан
    echo.
    echo ⚠️  ВАЖНО: Откройте файл .env и замените YOUR_TELEGRAM_ID
    echo    на ваш реальный Telegram ID
    echo.
    echo    Как узнать свой ID:
    echo    1. Откройте Telegram
    echo    2. Найдите бота @userinfobot
    echo    3. Отправьте /start
    echo    4. Скопируйте число (это ваш ID^)
    echo.
) else (
    echo ✅ Файл .env уже существует
    echo.
)

REM Создание папки для фото
if not exist photos (
    mkdir photos
    echo ✅ Папка photos создана
) else (
    echo ✅ Папка photos существует
)
echo.

REM Проверка настройки
echo [4/4] Проверка настройки...
python check_setup.py
echo.

echo ╔════════════════════════════════════════════════════════════╗
echo ║                  Установка завершена!                      ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo 📋 Следующие шаги:
echo.
echo 1. Откройте файл .env
echo 2. Замените YOUR_TELEGRAM_ID на ваш Telegram ID
echo 3. Запустите start.bat или выполните: python bot.py
echo.
echo 📖 Документация:
echo    - START_HERE.md - начните здесь
echo    - QUICKSTART.md - быстрый старт
echo    - README.md - полное описание
echo.
pause

