import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode

import config
import database as db
import admin
from admin import is_admin

# Настройка логирования
import logging.handlers

# Создаем директорию для логов
if not os.path.exists('logs'):
    os.makedirs('logs')

# Настройка логирования в файл и консоль
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
file_handler = logging.handlers.RotatingFileHandler(
    'logs/bot.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(log_format))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(log_format))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
GENDER, NAME, BIRTH_DATE, CITY, DESCRIPTION, PHOTO = range(6)
CHAT_MODE = 100

# Словарь для хранения активных чатов
user_chats = {}


async def check_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка админ прав (для отладки)"""
    user_id = update.effective_user.id
    is_admin_user = is_admin(user_id)
    
    await update.message.reply_text(
        f"🔍 Проверка админ прав:\n\n"
        f"Ваш Telegram ID: {user_id}\n"
        f"Админ ID в конфиге: {config.ADMIN_IDS}\n"
        f"Являетесь админом: {'✅ Да' if is_admin_user else '❌ Нет'}\n\n"
        f"Если вы админ, но кнопка не появляется, отправьте /start для обновления меню."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    if user:
        # Пользователь уже зарегистрирован
        if user.gender == 'male':
            await show_main_menu_male(update, context)
        else:
            await show_main_menu_female(update, context)
    else:
        # Начинаем регистрацию
        keyboard = [
            [InlineKeyboardButton("👨 Мужской", callback_data='gender_male')],
            [InlineKeyboardButton("👩 Женский", callback_data='gender_female')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👋 Добро пожаловать в бот знакомств!\n\n"
            "Для начала нужно заполнить анкету.\n"
            "Выберите ваш пол:",
            reply_markup=reply_markup
        )
        return GENDER


async def gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора пола"""
    query = update.callback_query
    await query.answer()
    
    gender = query.data.split('_')[1]
    context.user_data['gender'] = gender
    
    await query.edit_message_text(
        f"Отлично! Как вас зовут?\n"
        f"Напишите ваше имя:"
    )
    return NAME


async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик имени"""
    name = update.message.text.strip()
    
    # Валидация имени
    if len(name) < 2:
        await update.message.reply_text(
            "❌ Имя слишком короткое. Пожалуйста, укажите ваше имя (минимум 2 символа):"
        )
        return NAME
    
    if len(name) > 100:
        await update.message.reply_text(
            "❌ Имя слишком длинное. Пожалуйста, укажите имя до 100 символов:"
        )
        return NAME
    
    context.user_data['name'] = name
    
    await update.message.reply_text(
        f"Приятно познакомиться, {name}! Теперь укажите вашу дату рождения.\n"
        f"Формат: ДД.ММ.ГГГГ (например, 25.12.1995)"
    )
    return BIRTH_DATE


async def birth_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик даты рождения"""
    birth_date = update.message.text.strip()
    
    # Простая валидация
    if len(birth_date) != 10 or birth_date.count('.') != 2:
        await update.message.reply_text(
            "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ (например, 25.12.1995)"
        )
        return BIRTH_DATE
    
    context.user_data['birth_date'] = birth_date
    
    await update.message.reply_text(
        "Отлично! Теперь укажите ваш город:"
    )
    return CITY


async def city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик города"""
    city = update.message.text.strip()
    context.user_data['city'] = city
    
    await update.message.reply_text(
        "Теперь напишите описание вашей анкеты.\n"
        "Расскажите о себе, своих интересах, что ищете:"
    )
    return DESCRIPTION


async def description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик описания"""
    description = update.message.text.strip()
    context.user_data['description'] = description
    
    await update.message.reply_text(
        "Отлично! Теперь загрузите ваше фото:"
    )
    return PHOTO


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографии"""
    photo = update.message.photo[-1]
    
    # Сохраняем фото
    file = await context.bot.get_file(photo.file_id)
    file_path = os.path.join(config.PHOTOS_DIR, f"{update.effective_user.id}.jpg")
    await file.download_to_drive(file_path)
    
    # Создаем пользователя в БД
    user = db.create_user(
        telegram_id=update.effective_user.id,
        username=update.effective_user.username or "Без username",
        name=context.user_data['name'],
        gender=context.user_data['gender'],
        birth_date=context.user_data['birth_date'],
        city=context.user_data['city'],
        description=context.user_data['description'],
        photo_path=file_path
    )
    
    # Показываем клавиатуру в зависимости от пола
    if user.gender == 'male':
        keyboard = [
            [KeyboardButton("🔍 Смотреть анкеты")],
            [KeyboardButton("💬 Мои чаты")],
            [KeyboardButton("👤 Моя анкета")]
        ]
    else:
        keyboard = [
            [KeyboardButton("❤️ Уведомления о симпатиях")],
            [KeyboardButton("💬 Мои чаты")],
            [KeyboardButton("👤 Моя анкета")]
        ]
    
    # Добавляем кнопку админ панели, если пользователь админ
    if is_admin(update.effective_user.id):
        keyboard.append([KeyboardButton("🔧 Админ панель")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "✅ Регистрация завершена!\n"
        "Ваша анкета сохранена.",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END


async def show_main_menu_male(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню для мужчин"""
    keyboard = [
        [KeyboardButton("🔍 Смотреть анкеты")],
        [KeyboardButton("💬 Мои чаты")],
        [KeyboardButton("👤 Моя анкета")]
    ]
    
    # Добавляем кнопку админ панели, если пользователь админ
    if is_admin(update.effective_user.id):
        keyboard.append([KeyboardButton("🔧 Админ панель")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    message = update.message if update.message else update.callback_query.message
    await message.reply_text(
        "Главное меню:",
        reply_markup=reply_markup
    )


async def show_main_menu_female(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню для женщин"""
    keyboard = [
        [KeyboardButton("❤️ Уведомления о симпатиях")],
        [KeyboardButton("💬 Мои чаты")],
        [KeyboardButton("👤 Моя анкета")]
    ]
    
    # Добавляем кнопку админ панели, если пользователь админ
    if is_admin(update.effective_user.id):
        keyboard.append([KeyboardButton("🔧 Админ панель")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    message = update.message if update.message else update.callback_query.message
    await message.reply_text(
        "Главное меню:",
        reply_markup=reply_markup
    )


async def browse_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать следующую анкету"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    if user.gender != 'male':
        await update.message.reply_text("Эта функция доступна только для мужчин.")
        return
    
    # Получаем следующую анкету
    profiles = db.get_profiles_for_user(user.id, user.city, limit=1)
    
    if not profiles:
        await update.message.reply_text(
            "😔 К сожалению, больше нет доступных анкет.\n"
            "Попробуйте позже!"
        )
        return
    
    profile = profiles[0]
    
    # Формируем текст анкеты
    text = (
        f"👩 {profile.name}\n\n"
        f"Дата рождения: {profile.birth_date}\n"
        f"Город: {user.city}\n\n"  # Показываем город ПОЛЬЗОВАТЕЛЯ, а не девушки
        f"{profile.description}"
    )
    
    # Кнопки лайк/дизлайк
    keyboard = [
        [
            InlineKeyboardButton("❤️ Нравится", callback_data=f'like_{profile.id}'),
            InlineKeyboardButton("👎 Дальше", callback_data=f'dislike_{profile.id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем фото с описанием
    try:
        with open(profile.photo_path, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}")
        await update.message.reply_text(text, reply_markup=reply_markup)


async def like_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик лайка"""
    query = update.callback_query
    await query.answer()
    
    action, profile_id = query.data.split('_')
    profile_id = int(profile_id)
    
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    if action == 'like':
        # Добавляем лайк в БД
        like = db.add_like(user.id, profile_id)
        
        # Получаем профиль девушки
        session = db.get_session()
        try:
            profile = session.query(db.User).filter_by(id=profile_id).first()
            
            # Отправляем уведомление девушке
            keyboard = [
                [InlineKeyboardButton("👀 Посмотреть анкету", callback_data=f'view_like_{like.id}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=profile.telegram_id,
                text=f"❤️ У вас новая симпатия!\n\nКто-то проявил к вам интерес.",
                reply_markup=reply_markup
            )
        finally:
            session.close()
        
        await query.edit_message_caption(
            caption="❤️ Симпатия отправлена!\n\nНажмите '🔍 Смотреть анкеты' для продолжения."
        )
    
    elif action == 'dislike':
        # Добавляем в просмотренные
        db.add_viewed_profile(user.id, profile_id)
        await query.edit_message_caption(
            caption="👍 Анкета пропущена.\n\nНажмите '🔍 Смотреть анкеты' для продолжения."
        )


async def view_like_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр анкеты того, кто поставил лайк"""
    query = update.callback_query
    await query.answer()
    
    like_id = int(query.data.split('_')[2])
    
    # Отмечаем лайк как просмотренный
    db.mark_like_as_viewed(like_id)
    
    # Получаем информацию о лайке
    session = db.get_session()
    try:
        like = session.query(db.Like).filter_by(id=like_id).first()
        from_user = session.query(db.User).filter_by(id=like.from_user_id).first()
        to_user = session.query(db.User).filter_by(id=like.to_user_id).first()
        
        # Формируем текст анкеты
        text = (
            f"👨 {from_user.name}\n\n"
            f"Дата рождения: {from_user.birth_date}\n"
            f"Город: {to_user.city}\n\n"  # Показываем город девушки
            f"{from_user.description}"
        )
        
        # Кнопка начать диалог
        keyboard = [
            [InlineKeyboardButton("💬 Начать диалог", callback_data=f'start_chat_{like_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем фото с описанием
        try:
            with open(from_user.photo_path, 'rb') as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=text,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Ошибка при отправке фото: {e}")
            await query.message.reply_text(text, reply_markup=reply_markup)
        
        await query.edit_message_reply_markup(reply_markup=None)
    finally:
        session.close()


async def start_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать диалог после лайка"""
    query = update.callback_query
    await query.answer()
    
    like_id = int(query.data.split('_')[2])
    
    # Отмечаем что чат начат
    db.start_chat(like_id)
    
    # Получаем информацию о лайке
    session = db.get_session()
    try:
        like = session.query(db.Like).filter_by(id=like_id).first()
        from_user = session.query(db.User).filter_by(id=like.from_user_id).first()
        
        # Уведомляем мужчину
        await context.bot.send_message(
            chat_id=from_user.telegram_id,
            text=f"💬 Отличные новости!\n\nДевушка хочет начать с вами диалог.\n"
                 f"Перейдите в '💬 Мои чаты' чтобы начать общение."
        )
        
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ Диалог начат! Перейдите в '💬 Мои чаты'."
        )
    finally:
        session.close()


async def show_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать уведомления о симпатиях"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    if user.gender != 'female':
        await update.message.reply_text("Эта функция доступна только для женщин.")
        return
    
    likes = db.get_unviewed_likes(user.id)
    
    if not likes:
        await update.message.reply_text(
            "У вас пока нет новых симпатий 😊"
        )
        return
    
    await update.message.reply_text(
        f"❤️ У вас {len(likes)} новых симпатий!\n"
        f"Нажмите на кнопку ниже чтобы посмотреть анкеты:"
    )
    
    for like in likes:
        keyboard = [
            [InlineKeyboardButton("👀 Посмотреть анкету", callback_data=f'view_like_{like.id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Новая симпатия ждет вас!",
            reply_markup=reply_markup
        )


async def show_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные чаты"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    chats = db.get_active_chats(user.id)
    
    if not chats:
        await update.message.reply_text(
            "У вас пока нет активных чатов."
        )
        return
    
    await update.message.reply_text(
        f"💬 У вас {len(chats)} активных чатов.\n"
        f"Выберите чат:"
    )
    
    session = db.get_session()
    try:
        for like in chats:
            # Определяем с кем чат
            if like.from_user_id == user.id:
                chat_user = session.query(db.User).filter_by(id=like.to_user_id).first()
            else:
                chat_user = session.query(db.User).filter_by(id=like.from_user_id).first()
            
            keyboard = [
                [InlineKeyboardButton(
                    f"💬 Открыть чат", 
                    callback_data=f'open_chat_{chat_user.id}'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Показываем краткую инфо
            text = f"Чат с {chat_user.name}\nГород: {chat_user.city}"
            
            try:
                with open(chat_user.photo_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=reply_markup
                    )
            except:
                await update.message.reply_text(text, reply_markup=reply_markup)
    finally:
        session.close()


async def open_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть чат с пользователем"""
    query = update.callback_query
    await query.answer()
    
    chat_user_id = int(query.data.split('_')[2])
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    # Сохраняем активный чат пользователя
    user_chats[update.effective_user.id] = chat_user_id
    
    await query.message.reply_text(
        "💬 Чат открыт!\n\n"
        "Теперь все ваши сообщения будут отправляться собеседнику.\n"
        "Для выхода из чата используйте команду /exit"
    )


def get_chat_partner_telegram_id(chat_user_id: int):
    """Получить telegram_id собеседника в чате"""
    session = db.get_session()
    try:
        chat_user = session.query(db.User).filter_by(id=chat_user_id).first()
        if not chat_user:
            return None
        return chat_user.telegram_id
    finally:
        session.close()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    # Проверяем, зарегистрирован ли пользователь
    if not user:
        await update.message.reply_text(
            "❌ Вы не зарегистрированы. Отправьте /start для регистрации."
        )
        return
    
    # Проверяем, находится ли пользователь в режиме чата
    if update.effective_user.id in user_chats:
        chat_user_id = user_chats[update.effective_user.id]
        
        # Получаем telegram_id собеседника
        partner_telegram_id = get_chat_partner_telegram_id(chat_user_id)
        if not partner_telegram_id:
            await update.message.reply_text(
                "❌ Ошибка: собеседник не найден. Выйдите из чата и откройте его заново."
            )
            del user_chats[update.effective_user.id]
            return
        
        # Сохраняем сообщение в БД
        db.add_message(user.id, chat_user_id, text)
        
        # Отправляем сообщение собеседнику
        try:
            await context.bot.send_message(
                chat_id=partner_telegram_id,
                text=f"💬 {user.name}:\n\n{text}"
            )
            await update.message.reply_text("✅ Сообщение отправлено")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            await update.message.reply_text(
                f"❌ Не удалось отправить сообщение. Ошибка: {str(e)}"
            )
        return
    
    # Обработка кнопок меню
    if text == "🔍 Смотреть анкеты":
        await browse_profiles(update, context)
    elif text == "💬 Мои чаты":
        await show_chats(update, context)
    elif text == "❤️ Уведомления о симпатиях":
        await show_notifications(update, context)
    elif text == "👤 Моя анкета":
        await show_my_profile(update, context)
    elif text == "🔧 Админ панель":
        await admin.admin_menu(update, context)


async def show_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать свою анкету"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    text = (
        f"👤 Ваша анкета:\n\n"
        f"Имя: {user.name}\n"
        f"Пол: {'Мужской' if user.gender == 'male' else 'Женский'}\n"
        f"Дата рождения: {user.birth_date}\n"
        f"Город: {user.city}\n\n"
        f"{user.description}"
    )
    
    try:
        with open(user.photo_path, 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=text)
    except:
        await update.message.reply_text(text)


async def exit_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выйти из чата"""
    if update.effective_user.id in user_chats:
        del user_chats[update.effective_user.id]
        await update.message.reply_text("Вы вышли из чата.")
    else:
        await update.message.reply_text("Вы не находитесь в чате.")


async def handle_photo_in_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото в чате"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    # Проверяем, зарегистрирован ли пользователь
    if not user:
        await update.message.reply_text(
            "❌ Вы не зарегистрированы. Отправьте /start для регистрации."
        )
        return
    
    # Проверяем, находится ли пользователь в режиме чата
    if update.effective_user.id not in user_chats:
        return  # Не в режиме чата, игнорируем
    
    chat_user_id = user_chats[update.effective_user.id]
    photo = update.message.photo[-1]  # Берем фото наибольшего размера
    caption = update.message.caption or ""
    
    # Получаем telegram_id собеседника
    partner_telegram_id = get_chat_partner_telegram_id(chat_user_id)
    if not partner_telegram_id:
        await update.message.reply_text(
            "❌ Ошибка: собеседник не найден. Выйдите из чата и откройте его заново."
        )
        del user_chats[update.effective_user.id]
        return
    
    # Сохраняем сообщение в БД (если есть подпись)
    if caption:
        db.add_message(user.id, chat_user_id, f"[Фото] {caption}")
    else:
        db.add_message(user.id, chat_user_id, "[Фото]")
    
    # Отправляем фото собеседнику
    try:
        if caption:
            await context.bot.send_photo(
                chat_id=partner_telegram_id,
                photo=photo.file_id,
                caption=f"📷 {user.name}:\n\n{caption}"
            )
        else:
            await context.bot.send_photo(
                chat_id=partner_telegram_id,
                photo=photo.file_id,
                caption=f"📷 {user.name}"
            )
        await update.message.reply_text("✅ Фото отправлено")
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}")
        await update.message.reply_text(
            f"❌ Не удалось отправить фото. Ошибка: {str(e)}"
        )


async def handle_video_in_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик видео в чате"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    # Проверяем, зарегистрирован ли пользователь
    if not user:
        await update.message.reply_text(
            "❌ Вы не зарегистрированы. Отправьте /start для регистрации."
        )
        return
    
    # Проверяем, находится ли пользователь в режиме чата
    if update.effective_user.id not in user_chats:
        return  # Не в режиме чата, игнорируем
    
    chat_user_id = user_chats[update.effective_user.id]
    video = update.message.video
    caption = update.message.caption or ""
    
    # Получаем telegram_id собеседника
    partner_telegram_id = get_chat_partner_telegram_id(chat_user_id)
    if not partner_telegram_id:
        await update.message.reply_text(
            "❌ Ошибка: собеседник не найден. Выйдите из чата и откройте его заново."
        )
        del user_chats[update.effective_user.id]
        return
    
    # Сохраняем сообщение в БД (если есть подпись)
    if caption:
        db.add_message(user.id, chat_user_id, f"[Видео] {caption}")
    else:
        db.add_message(user.id, chat_user_id, "[Видео]")
    
    # Отправляем видео собеседнику
    try:
        if caption:
            await context.bot.send_video(
                chat_id=partner_telegram_id,
                video=video.file_id,
                caption=f"🎥 {user.name}:\n\n{caption}"
            )
        else:
            await context.bot.send_video(
                chat_id=partner_telegram_id,
                video=video.file_id,
                caption=f"🎥 {user.name}"
            )
        await update.message.reply_text("✅ Видео отправлено")
    except Exception as e:
        logger.error(f"Ошибка при отправке видео: {e}")
        await update.message.reply_text(
            f"❌ Не удалось отправить видео. Ошибка: {str(e)}"
        )


async def handle_document_in_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов/файлов в чате"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    # Проверяем, зарегистрирован ли пользователь
    if not user:
        await update.message.reply_text(
            "❌ Вы не зарегистрированы. Отправьте /start для регистрации."
        )
        return
    
    # Проверяем, находится ли пользователь в режиме чата
    if update.effective_user.id not in user_chats:
        return  # Не в режиме чата, игнорируем
    
    chat_user_id = user_chats[update.effective_user.id]
    document = update.message.document
    caption = update.message.caption or ""
    
    # Получаем telegram_id собеседника
    partner_telegram_id = get_chat_partner_telegram_id(chat_user_id)
    if not partner_telegram_id:
        await update.message.reply_text(
            "❌ Ошибка: собеседник не найден. Выйдите из чата и откройте его заново."
        )
        del user_chats[update.effective_user.id]
        return
    
    # Сохраняем сообщение в БД
    file_name = document.file_name or "файл"
    if caption:
        db.add_message(user.id, chat_user_id, f"[Файл: {file_name}] {caption}")
    else:
        db.add_message(user.id, chat_user_id, f"[Файл: {file_name}]")
    
    # Отправляем файл собеседнику
    try:
        if caption:
            await context.bot.send_document(
                chat_id=partner_telegram_id,
                document=document.file_id,
                caption=f"📎 {user.name}:\n\n{caption}"
            )
        else:
            await context.bot.send_document(
                chat_id=partner_telegram_id,
                document=document.file_id,
                caption=f"📎 {user.name}"
            )
        await update.message.reply_text("✅ Файл отправлен")
    except Exception as e:
        logger.error(f"Ошибка при отправке файла: {e}")
        await update.message.reply_text(
            f"❌ Не удалось отправить файл. Ошибка: {str(e)}"
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена регистрации"""
    await update.message.reply_text("Регистрация отменена.")
    return ConversationHandler.END


def main():
    """Запуск бота"""
    # Проверка токена
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN не указан в .env файле!")
        return
    
    # Инициализация БД
    try:
        db.init_db()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        return
    
    # Создание приложения
    try:
        application = Application.builder().token(config.BOT_TOKEN).build()
        logger.info("Приложение создано")
    except Exception as e:
        logger.error(f"Ошибка создания приложения: {e}")
        return
    
    # Обработчик регистрации
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GENDER: [CallbackQueryHandler(gender_callback, pattern='^gender_')],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, birth_date_handler)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city_handler)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_handler)],
            PHOTO: [MessageHandler(filters.PHOTO, photo_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    
    # Настройка админ обработчиков
    admin.setup_admin_handlers(application)
    
    # Обработчики callback
    application.add_handler(CallbackQueryHandler(like_callback, pattern='^(like|dislike)_'))
    application.add_handler(CallbackQueryHandler(view_like_callback, pattern='^view_like_'))
    application.add_handler(CallbackQueryHandler(start_chat_callback, pattern='^start_chat_'))
    application.add_handler(CallbackQueryHandler(open_chat_callback, pattern='^open_chat_'))
    
    # Обработчики команд
    application.add_handler(CommandHandler('exit', exit_chat))
    application.add_handler(CommandHandler('checkadmin', check_admin))  # Для отладки
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчики медиа в чате (только если не в процессе регистрации)
    # Используем фильтр, чтобы не перехватывать фото при регистрации
    application.add_handler(MessageHandler(
        filters.PHOTO & ~filters.COMMAND, 
        handle_photo_in_chat
    ))
    application.add_handler(MessageHandler(
        filters.VIDEO & ~filters.COMMAND, 
        handle_video_in_chat
    ))
    application.add_handler(MessageHandler(
        filters.Document.ALL & ~filters.COMMAND, 
        handle_document_in_chat
    ))
    
    # Запуск бота
    try:
        logger.info("Бот запущен!")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True  # Пропускать обновления при старте
        )
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise


if __name__ == '__main__':
    main()

