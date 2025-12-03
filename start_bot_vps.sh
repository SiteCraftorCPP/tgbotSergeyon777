#!/bin/bash
# Команды для запуска бота на VPS

cd ~/tgbotSergeyon777
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &

echo "Бот запущен в фоне. PID: $!"
echo "Проверить логи: tail -f bot.log"
echo "Остановить бота: pkill -f 'python.*bot.py'"


