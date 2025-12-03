#!/bin/bash

# Команды для обновления бота на VPS с GitHub

# 1. Перейти в директорию проекта
cd ~/tgbotSergeyon777

# 2. Остановить бота (если запущен через systemd)
sudo systemctl stop dating-bot

# ИЛИ если бот запущен через nohup/screen, найти и остановить процесс:
# pkill -f "python.*bot.py"

# 3. Получить обновления с GitHub
git pull origin main

# 4. Активировать виртуальное окружение (если используется)
source venv/bin/activate

# 5. Обновить зависимости (если requirements.txt изменился)
# pip install -r requirements.txt

# 6. Запустить бота через systemd
sudo systemctl start dating-bot

# ИЛИ запустить вручную в фоне:
# nohup python3 bot.py > bot.log 2>&1 &

# 7. Проверить статус бота
sudo systemctl status dating-bot

# ИЛИ проверить логи:
# tail -f bot.log


