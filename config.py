import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

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

DATABASE_URL = 'sqlite:///dating_bot.db'
PHOTOS_DIR = 'photos'

# Создаем директорию для фотографий
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

