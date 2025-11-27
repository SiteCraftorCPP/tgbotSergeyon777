#!/bin/bash

echo "===================================="
echo "  Запуск бота для знакомств"
echo "===================================="
echo ""

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "[ОШИБКА] Файл .env не найден!"
    echo ""
    echo "Создайте файл .env со следующим содержимым:"
    echo "BOT_TOKEN=7682201960:AAEAS4510i6bOR3wq0taMdaq--SqnqRiR9U"
    echo "ADMIN_ID=YOUR_TELEGRAM_ID"
    echo ""
    echo "Замените YOUR_TELEGRAM_ID на ваш Telegram ID"
    echo "Чтобы узнать свой ID, напишите боту @userinfobot"
    echo ""
    exit 1
fi

echo "Запуск бота..."
python bot.py

