import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

# ЮKassa API настройки
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID', '0')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY', 'live_rQivMWcqdtivU4TDbP4w-fyX5mwyFqEQR582FY7HDsM')

# Цены подписок (в рублях)
SUBSCRIPTION_PRICE_1_DAY = 10  # Пробная подписка на 1 день
SUBSCRIPTION_PRICE_1_MONTH = 999  # Месячная подписка

# Поддержка нескольких администраторов
# Можно указать через запятую: ADMIN_IDS=123456789,987654321
admin_ids_str = os.getenv('ADMIN_IDS', '')
if admin_ids_str:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]
else:
    # Если ADMIN_IDS не указан, используем ADMIN_ID (для обратной совместимости)
    ADMIN_IDS = [ADMIN_ID] if ADMIN_ID else []

# Добавляем пользователя 6933111964 в список админов
if 6933111964 not in ADMIN_IDS:
    ADMIN_IDS.append(6933111964)

# Поддержка PostgreSQL для продакшена
# Если указан DATABASE_URL, используем его, иначе SQLite
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///dating_bot.db')
# Конвертируем postgres:// в postgresql:// для SQLAlchemy
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

PHOTOS_DIR = os.getenv('PHOTOS_DIR', 'photos')

# Создаем директорию для фотографий
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

