#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для проверки правильности настройки бота
"""

import os
import sys

def check_python_version():
    """Проверка версии Python"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python версии 3.8 или выше не найден")
        print(f"   Текущая версия: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Проверка установленных зависимостей"""
    required = {
        'telegram': 'python-telegram-bot',
        'sqlalchemy': 'SQLAlchemy',
        'dotenv': 'python-dotenv',
        'PIL': 'Pillow'
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
            print(f"✅ {package} установлен")
        except ImportError:
            print(f"❌ {package} не установлен")
            missing.append(package)
    
    if missing:
        print("\n⚠️  Установите недостающие пакеты:")
        print("   pip install -r requirements.txt")
        return False
    
    return True


def check_env_file():
    """Проверка наличия .env файла"""
    if not os.path.exists('.env'):
        print("❌ Файл .env не найден")
        print("\n   Создайте файл .env со следующим содержимым:")
        print("   BOT_TOKEN=7682201960:AAEAS4510i6bOR3wq0taMdaq--SqnqRiR9U")
        print("   ADMIN_ID=YOUR_TELEGRAM_ID")
        print("\n   Замените YOUR_TELEGRAM_ID на ваш Telegram ID")
        print("   Чтобы узнать свой ID: https://t.me/userinfobot")
        return False
    
    print("✅ Файл .env найден")
    
    # Проверяем содержимое
    from dotenv import load_dotenv
    load_dotenv()
    
    bot_token = os.getenv('BOT_TOKEN')
    admin_id = os.getenv('ADMIN_ID')
    
    if not bot_token:
        print("❌ BOT_TOKEN не указан в .env")
        return False
    print(f"✅ BOT_TOKEN найден ({bot_token[:10]}...)")
    
    if not admin_id or admin_id == 'YOUR_TELEGRAM_ID':
        print("⚠️  ADMIN_ID не указан или не изменен")
        print("   Админ панель не будет работать")
        print("   Узнайте свой ID: https://t.me/userinfobot")
    else:
        print(f"✅ ADMIN_ID найден ({admin_id})")
    
    return True


def check_files():
    """Проверка наличия необходимых файлов"""
    required_files = ['bot.py', 'database.py', 'admin.py', 'config.py']
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Файл {file} не найден")
            return False
        print(f"✅ {file}")
    
    return True


def check_directories():
    """Проверка/создание необходимых директорий"""
    if not os.path.exists('photos'):
        print("⚠️  Папка photos/ не найдена, создаю...")
        os.makedirs('photos')
        print("✅ Папка photos/ создана")
    else:
        print("✅ Папка photos/ найдена")
    
    return True


def main():
    print("="*50)
    print("🔍 Проверка настройки бота для знакомств")
    print("="*50)
    print()
    
    checks = [
        ("Python версия", check_python_version),
        ("Зависимости", check_dependencies),
        (".env файл", check_env_file),
        ("Необходимые файлы", check_files),
        ("Директории", check_directories),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n📋 Проверка: {name}")
        print("-" * 50)
        result = check_func()
        results.append(result)
        print()
    
    print("="*50)
    if all(results):
        print("✅ Все проверки пройдены!")
        print("\n🚀 Можно запускать бота:")
        print("   python bot.py")
    else:
        print("❌ Некоторые проверки не пройдены")
        print("\n⚠️  Исправьте ошибки перед запуском бота")
    print("="*50)


if __name__ == '__main__':
    main()

