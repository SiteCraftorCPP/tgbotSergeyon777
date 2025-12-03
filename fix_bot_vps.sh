#!/bin/bash
# Команды для диагностики и исправления бота на VPS

echo "=== Диагностика бота ==="

# 1. Остановить бота
echo "1. Останавливаю бота..."
pkill -f "python.*bot.py"
sleep 2

# 2. Проверить последние логи
echo "2. Последние 50 строк логов:"
tail -50 bot.log

# 3. Проверить ошибки в логах
echo ""
echo "3. Ошибки в логах:"
grep -i "error\|exception\|traceback" bot.log | tail -20

# 4. Удалить старую БД и пересоздать (если проблема с схемой)
echo ""
echo "4. ВНИМАНИЕ: Если проблема в базе данных, выполните:"
echo "   rm dating_bot.db"
echo "   (Бот пересоздаст БД при запуске)"

# 5. Запустить бота заново
echo ""
echo "5. Запускаю бота..."
cd ~/tgbotSergeyon777
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &

sleep 3

# 6. Проверить статус
echo ""
echo "6. Статус процесса:"
ps aux | grep "python.*bot.py" | grep -v grep

# 7. Посмотреть новые логи
echo ""
echo "7. Новые логи (последние 20 строк):"
tail -20 bot.log


