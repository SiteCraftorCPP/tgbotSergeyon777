@echo off
echo ====================================
echo  Запуск бота для знакомств
echo ====================================
echo.

REM Проверка наличия .env файла
if not exist .env (
    echo [ОШИБКА] Файл .env не найден!
    echo.
    echo Создайте файл .env со следующим содержимым:
    echo BOT_TOKEN=7682201960:AAEAS4510i6bOR3wq0taMdaq--SqnqRiR9U
    echo ADMIN_ID=YOUR_TELEGRAM_ID
    echo.
    echo Замените YOUR_TELEGRAM_ID на ваш Telegram ID
    echo Чтобы узнать свой ID, напишите боту @userinfobot
    echo.
    pause
    exit /b 1
)

echo Запуск бота...
python bot.py

pause

