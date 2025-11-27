#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

clear

echo "╔════════════════════════════════════════════════════════════╗"
echo "║        Установка Telegram Бота для Знакомств              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Проверка Python
echo "[1/4] Проверка Python..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 не найден!${NC}"
    echo ""
    echo "Установите Python 3.8 или выше:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  Fedora: sudo dnf install python3 python3-pip"
    echo "  macOS: brew install python3"
    echo ""
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2)
echo -e "${GREEN}✅ Python $PYTHON_VERSION найден${NC}"
echo ""

# Установка зависимостей
echo "[2/4] Установка зависимостей..."
python3 -m pip install --upgrade pip > /dev/null 2>&1
python3 -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка при установке зависимостей${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Зависимости установлены${NC}"
echo ""

# Создание .env файла
echo "[3/4] Настройка конфигурации..."
if [ ! -f .env ]; then
    cat > .env << EOF
BOT_TOKEN=7682201960:AAEAS4510i6bOR3wq0taMdaq--SqnqRiR9U
ADMIN_ID=YOUR_TELEGRAM_ID
EOF
    echo -e "${GREEN}✅ Файл .env создан${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  ВАЖНО: Откройте файл .env и замените YOUR_TELEGRAM_ID${NC}"
    echo "   на ваш реальный Telegram ID"
    echo ""
    echo "   Как узнать свой ID:"
    echo "   1. Откройте Telegram"
    echo "   2. Найдите бота @userinfobot"
    echo "   3. Отправьте /start"
    echo "   4. Скопируйте число (это ваш ID)"
    echo ""
else
    echo -e "${GREEN}✅ Файл .env уже существует${NC}"
    echo ""
fi

# Создание папки для фото
if [ ! -d "photos" ]; then
    mkdir photos
    echo -e "${GREEN}✅ Папка photos создана${NC}"
else
    echo -e "${GREEN}✅ Папка photos существует${NC}"
fi
echo ""

# Делаем скрипты исполняемыми
chmod +x start.sh

# Проверка настройки
echo "[4/4] Проверка настройки..."
python3 check_setup.py
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  Установка завершена!                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Следующие шаги:"
echo ""
echo "1. Откройте файл .env"
echo "   nano .env"
echo ""
echo "2. Замените YOUR_TELEGRAM_ID на ваш Telegram ID"
echo ""
echo "3. Запустите: ./start.sh или python3 bot.py"
echo ""
echo "📖 Документация:"
echo "   - START_HERE.md - начните здесь"
echo "   - QUICKSTART.md - быстрый старт"
echo "   - README.md - полное описание"
echo ""

