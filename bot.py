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
GENDER, NAME, AGE, CITY, DESCRIPTION, PHOTO = range(6)
CHAT_MODE = 100
HASHTAG_SEARCH = 101  # Состояние для поиска по хэштэгу

# Словарь для хранения активных чатов {telegram_id: chat_user_id}
user_chats = {}

# Словарь для хранения информации о текущем собеседнике {telegram_id: partner_user_object}
active_chat_info = {}


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
    
    # Проверяем, был ли пользователь в процессе регистрации
    was_in_registration = bool(context.user_data)
    
    # Очищаем данные предыдущей незавершенной регистрации
    context.user_data.clear()
    
    if user:
        # Пользователь уже зарегистрирован
        if was_in_registration:
            # Если была незавершенная регистрация, сообщаем об этом
            await update.message.reply_text(
                "✅ Предыдущая незавершенная регистрация была сброшена.\n\n"
            )
        if user.gender == 'male':
            await show_main_menu_male(update, context)
        else:
            await show_main_menu_female(update, context)
        return ConversationHandler.END
    else:
        # Начинаем регистрацию
        message_text = "👋 Добро пожаловать в бот знакомств!\n\n"
        if was_in_registration:
            message_text += "✅ Предыдущая незавершенная регистрация была сброшена.\n\n"
        message_text += "Для начала нужно заполнить анкету.\nВыберите ваш пол:"
        
        keyboard = [
            [InlineKeyboardButton("👨 Мужской", callback_data='gender_male')],
            [InlineKeyboardButton("👩 Женский", callback_data='gender_female')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message_text,
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
        f"Приятно познакомиться, {name}! 🎂\n\n"
        f"Сколько вам лет? Напишите число:"
    )
    return AGE


async def age_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик возраста"""
    age_text = update.message.text.strip()
    
    # Валидация возраста
    try:
        age = int(age_text)
        if age < 18:
            await update.message.reply_text(
                "❌ Регистрация доступна только для пользователей старше 18 лет."
            )
            return AGE
        if age > 100:
            await update.message.reply_text(
                "❌ Пожалуйста, укажите корректный возраст."
            )
            return AGE
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите число (например: 22)"
        )
        return AGE
    
    context.user_data['age'] = age
    
    await update.message.reply_text(
        "🏙 Отлично! Теперь укажите ваш город:"
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
        age=context.user_data['age'],
        city=context.user_data['city'],
        description=context.user_data['description'],
        photo_path=file_path
    )
    
    # Показываем клавиатуру в зависимости от пола
    if user.gender == 'male':
        keyboard = [
            [KeyboardButton("🔍 Смотреть анкеты")],
            [KeyboardButton("🔍 Поиск по коду")],
            [KeyboardButton("💬 Мои чаты")],
            [KeyboardButton("👤 Моя анкета")]
        ]
        welcome_text = "✅ Регистрация завершена!\nВаша анкета сохранена."
    else:
        keyboard = [
            [KeyboardButton("❤️ Уведомления о симпатиях")],
            [KeyboardButton("💬 Мои чаты")],
            [KeyboardButton("👤 Моя анкета")]
        ]
        # Показываем хэштэг для женщин
        welcome_text = (
            f"✅ Регистрация завершена!\n"
            f"Ваша анкета сохранена.\n\n"
            f"🏷 Ваш уникальный код: {user.hashtag}\n"
            f"Мужчины могут найти вас по этому коду!"
        )
    
    # Добавляем кнопку админ панели, если пользователь админ
    if is_admin(update.effective_user.id):
        keyboard.append([KeyboardButton("🔧 Админ панель")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END


async def show_main_menu_male(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню для мужчин"""
    keyboard = [
        [KeyboardButton("🔍 Смотреть анкеты")],
        [KeyboardButton("🔍 Поиск по коду")],
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
        f"👩 {profile.name}, {profile.age}\n"
        f"📍 {user.city}\n\n"  # Показываем город ПОЛЬЗОВАТЕЛЯ, а не девушки
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
            
            try:
                logger.info(f"Отправка уведомления о симпатии: от {user.name} (TG: {user.telegram_id}) к {profile.name} (TG: {profile.telegram_id})")
                await context.bot.send_message(
                    chat_id=profile.telegram_id,
                    text=f"❤️ У вас новая симпатия!\n\nКто-то проявил к вам интерес.",
                    reply_markup=reply_markup
                )
                logger.info(f"Уведомление о симпатии успешно отправлено {profile.name} (TG: {profile.telegram_id})")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления о симпатии к {profile.name} (TG: {profile.telegram_id}): {e}")
                # Не показываем ошибку отправителю, просто логируем
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
            f"👨 {from_user.name}, {from_user.age}\n"
            f"📍 {to_user.city}\n\n"  # Показываем город девушки
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
        to_user = session.query(db.User).filter_by(id=like.to_user_id).first()
        
        # Уведомляем мужчину
        try:
            logger.info(f"Отправка уведомления о начале чата: от девушки {to_user.name} (TG: {to_user.telegram_id}) к мужчине {from_user.name} (TG: {from_user.telegram_id})")
            await context.bot.send_message(
                chat_id=from_user.telegram_id,
                text=f"💬 Отличные новости!\n\nДевушка хочет начать с вами диалог.\n"
                     f"Перейдите в '💬 Мои чаты' чтобы начать общение."
            )
            logger.info(f"Уведомление успешно отправлено мужчине {from_user.name} (TG: {from_user.telegram_id})")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления мужчине {from_user.name} (TG: {from_user.telegram_id}): {e}")
        
        # Уведомляем девушку, что чат начат
        try:
            logger.info(f"Отправка уведомления девушке {to_user.name} (TG: {to_user.telegram_id}) о начале чата")
            await context.bot.send_message(
                chat_id=to_user.telegram_id,
                text=f"✅ Диалог начат!\n\nВы можете начать общение с {from_user.name}.\n"
                     f"Перейдите в '💬 Мои чаты' чтобы начать переписку."
            )
            logger.info(f"Уведомление успешно отправлено девушке {to_user.name} (TG: {to_user.telegram_id})")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления девушке {to_user.name} (TG: {to_user.telegram_id}): {e}")
        
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
    """Показать активные чаты с красивым интерфейсом"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    # Проверяем, зарегистрирован ли пользователь
    if not user:
        logger.warning(f"Пользователь {update.effective_user.id} не зарегистрирован при попытке открыть чаты")
        await update.message.reply_text(
            "❌ Вы не зарегистрированы. Отправьте /start для регистрации."
        )
        return
    
    try:
        chats = db.get_active_chats(user.id)
    except Exception as e:
        logger.error(f"Ошибка при получении активных чатов для пользователя {user.id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при загрузке чатов. Попробуйте позже."
        )
        return
    
    # Проверяем, находится ли пользователь в чате
    current_chat_user_id = user_chats.get(update.effective_user.id)
    
    if not chats:
        await update.message.reply_text(
            "📭 У вас пока нет активных чатов.\n\n"
            "Чтобы начать общение:\n"
            "• Мужчины: поставьте ❤️ понравившейся анкете\n"
            "• Женщины: дождитесь симпатии и нажмите 'Начать диалог'"
        )
        return
    
    # Формируем красивый список чатов с кнопками
    chat_buttons = []
    session = db.get_session()
    try:
        for like in chats:
            # Определяем с кем чат
            if like.from_user_id == user.id:
                chat_user = session.query(db.User).filter_by(id=like.to_user_id).first()
            else:
                chat_user = session.query(db.User).filter_by(id=like.from_user_id).first()
            
            if not chat_user:
                continue
            
            # Формируем текст кнопки
            gender_emoji = "👨" if chat_user.gender == 'male' else "👩"
            active_marker = " ✅" if current_chat_user_id == chat_user.id else ""
            
            button_text = f"{gender_emoji} {chat_user.name}, {chat_user.age}{active_marker}"
            
            chat_buttons.append([
                InlineKeyboardButton(
                    button_text, 
                    callback_data=f'open_chat_{chat_user.id}'
                )
            ])
        
        # Добавляем кнопку выхода из чата, если пользователь сейчас в чате
        if current_chat_user_id:
            chat_buttons.append([
                InlineKeyboardButton("🚪 Выйти из текущего чата", callback_data='exit_current_chat')
            ])
        
        reply_markup = InlineKeyboardMarkup(chat_buttons)
        
        # Информация о текущем чате
        if current_chat_user_id:
            current_partner = db.get_user_by_id(current_chat_user_id)
            if current_partner:
                current_chat_info = f"\n\n💬 Сейчас вы пишете: {current_partner.name}"
            else:
                current_chat_info = ""
        else:
            current_chat_info = "\n\n💡 Выберите чат, чтобы начать переписку"
        
        await update.message.reply_text(
            f"💬 Ваши чаты ({len(chats)}){current_chat_info}",
            reply_markup=reply_markup
        )
    finally:
        session.close()


async def open_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть чат с пользователем - показать аватарку и красивый интерфейс"""
    query = update.callback_query
    await query.answer()
    
    chat_user_id = int(query.data.split('_')[2])
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    # Получаем информацию о собеседнике
    chat_partner = db.get_user_by_id(chat_user_id)
    if not chat_partner:
        await query.message.reply_text("❌ Пользователь не найден.")
        return
    
    # Сохраняем активный чат пользователя
    user_chats[update.effective_user.id] = chat_user_id
    active_chat_info[update.effective_user.id] = chat_partner
    
    logger.info(f"Чат открыт: пользователь {user.name} (ID: {user.id}, пол: {user.gender}, TG: {user.telegram_id}) открыл чат с {chat_partner.name} (ID: {chat_partner.id}, пол: {chat_partner.gender}, TG: {chat_partner.telegram_id})")
    
    # Отмечаем сообщения как прочитанные
    db.mark_messages_as_read(user.id, chat_user_id)
    
    # Уведомляем собеседника, что пользователь подключился к чату
    try:
        gender_emoji = "👨" if user.gender == 'male' else "👩"
        await context.bot.send_message(
            chat_id=chat_partner.telegram_id,
            text=f"💬 {gender_emoji} {user.name} подключился(ась) к чату.\n\nТеперь вы можете общаться!"
        )
        logger.info(f"Уведомление о подключении к чату отправлено {chat_partner.name} (TG: {chat_partner.telegram_id})")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о подключении к чату {chat_partner.name} (TG: {chat_partner.telegram_id}): {e}")
    
    gender_emoji = "👨" if chat_partner.gender == 'male' else "👩"
    
    # Кнопки управления чатом
    keyboard = [
        [
            InlineKeyboardButton("📋 Все чаты", callback_data='show_all_chats'),
            InlineKeyboardButton("🚪 Выйти", callback_data='exit_current_chat')
        ],
        [
            InlineKeyboardButton("👤 Анкета собеседника", callback_data=f'view_partner_{chat_user_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Формируем красивое сообщение с аватаркой
    text = (
        f"💬 Чат открыт!\n\n"
        f"{gender_emoji} {chat_partner.name}, {chat_partner.age}\n"
        f"📍 {chat_partner.city}\n\n"
        f"✏️ Теперь все ваши сообщения отправляются {chat_partner.name}.\n"
        f"Просто пишите текст, отправляйте фото или видео!"
    )
    
    # Отправляем аватарку собеседника с информацией
    try:
        with open(chat_partner.photo_path, 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}")
        await query.message.reply_text(text, reply_markup=reply_markup)


async def exit_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выйти из текущего чата (callback)"""
    query = update.callback_query
    await query.answer()
    
    user = db.get_user_by_telegram_id(update.effective_user.id)
    chat_partner = None
    
    # Получаем информацию о собеседнике перед выходом
    if update.effective_user.id in user_chats:
        chat_user_id = user_chats[update.effective_user.id]
        chat_partner = db.get_user_by_id(chat_user_id)
        del user_chats[update.effective_user.id]
    
    if update.effective_user.id in active_chat_info:
        del active_chat_info[update.effective_user.id]
    
    # Уведомляем собеседника, что пользователь покинул чат
    if chat_partner and user:
        try:
            gender_emoji = "👨" if user.gender == 'male' else "👩"
            await context.bot.send_message(
                chat_id=chat_partner.telegram_id,
                text=f"🚪 {gender_emoji} {user.name} покинул(а) чат."
            )
            logger.info(f"Уведомление о выходе из чата отправлено {chat_partner.name} (TG: {chat_partner.telegram_id})")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о выходе из чата {chat_partner.name} (TG: {chat_partner.telegram_id}): {e}")
    
    await query.message.reply_text(
        "🚪 Вы вышли из чата.\n\n"
        "Нажмите '💬 Мои чаты' чтобы выбрать другой чат."
    )


async def show_all_chats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все чаты (callback версия)"""
    query = update.callback_query
    await query.answer()
    
    user = db.get_user_by_telegram_id(update.effective_user.id)
    chats = db.get_active_chats(user.id)
    
    current_chat_user_id = user_chats.get(update.effective_user.id)
    
    if not chats:
        await query.message.reply_text("📭 У вас пока нет активных чатов.")
        return
    
    chat_buttons = []
    session = db.get_session()
    try:
        for like in chats:
            if like.from_user_id == user.id:
                chat_user = session.query(db.User).filter_by(id=like.to_user_id).first()
            else:
                chat_user = session.query(db.User).filter_by(id=like.from_user_id).first()
            
            if not chat_user:
                continue
            
            gender_emoji = "👨" if chat_user.gender == 'male' else "👩"
            active_marker = " ✅" if current_chat_user_id == chat_user.id else ""
            
            button_text = f"{gender_emoji} {chat_user.name}, {chat_user.age}{active_marker}"
            
            chat_buttons.append([
                InlineKeyboardButton(button_text, callback_data=f'open_chat_{chat_user.id}')
            ])
        
        if current_chat_user_id:
            chat_buttons.append([
                InlineKeyboardButton("🚪 Выйти из текущего чата", callback_data='exit_current_chat')
            ])
        
        reply_markup = InlineKeyboardMarkup(chat_buttons)
        
        if current_chat_user_id:
            current_partner = db.get_user_by_id(current_chat_user_id)
            if current_partner:
                current_chat_info = f"\n\n💬 Сейчас вы пишете: {current_partner.name}"
            else:
                current_chat_info = ""
        else:
            current_chat_info = "\n\n💡 Выберите чат, чтобы начать переписку"
        
        await query.message.reply_text(
            f"💬 Ваши чаты ({len(chats)}){current_chat_info}",
            reply_markup=reply_markup
        )
    finally:
        session.close()


async def view_partner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Посмотреть анкету собеседника"""
    query = update.callback_query
    await query.answer()
    
    partner_id = int(query.data.split('_')[2])
    partner = db.get_user_by_id(partner_id)
    
    if not partner:
        await query.message.reply_text("❌ Пользователь не найден.")
        return
    
    gender_emoji = "👨" if partner.gender == 'male' else "👩"
    text = (
        f"{gender_emoji} {partner.name}, {partner.age}\n"
        f"📍 {partner.city}\n\n"
        f"{partner.description}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться к чату", callback_data=f'open_chat_{partner_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        with open(partner.photo_path, 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}")
        await query.message.reply_text(text, reply_markup=reply_markup)


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
    
    logger.info(f"Получено сообщение от пользователя: {update.effective_user.id}, текст: {text[:50]}")
    
    # Проверяем, зарегистрирован ли пользователь
    if not user:
        logger.warning(f"Пользователь {update.effective_user.id} не зарегистрирован")
        await update.message.reply_text(
            "❌ Вы не зарегистрированы. Отправьте /start для регистрации."
        )
        return
    
    logger.info(f"Пользователь найден: {user.name} (ID: {user.id}, пол: {user.gender}, TG: {user.telegram_id})")
    
    # Список кнопок меню - если текст является кнопкой меню, обрабатываем как команду, а не отправляем в чат
    menu_buttons = [
        "🔍 Смотреть анкеты",
        "🔍 Поиск по коду",
        "💬 Мои чаты",
        "❤️ Уведомления о симпатиях",
        "👤 Моя анкета",
        "🔧 Админ панель"
    ]
    
    # Если это кнопка меню - обрабатываем как команду меню, не отправляем в чат
    if text in menu_buttons:
        logger.info(f"Пользователь {user.name} нажал кнопку меню: {text}")
        # Выходим из режима поиска по хэштэгу при нажатии любой кнопки меню
        hashtag_search_mode.pop(update.effective_user.id, None)
        
        # Обработка кнопок меню
        if text == "🔍 Смотреть анкеты":
            await browse_profiles(update, context)
        elif text == "🔍 Поиск по коду":
            await start_hashtag_search(update, context)
        elif text == "💬 Мои чаты":
            await show_chats(update, context)
        elif text == "❤️ Уведомления о симпатиях":
            await show_notifications(update, context)
        elif text == "👤 Моя анкета":
            await show_my_profile(update, context)
        elif text == "🔧 Админ панель":
            await admin.admin_menu(update, context)
        return
    
    # Проверяем, находится ли пользователь в режиме поиска по хэштэгу
    if update.effective_user.id in hashtag_search_mode:
        await process_hashtag_search(update, context)
        return
    
    # Проверяем, находится ли пользователь в режиме чата
    if update.effective_user.id in user_chats:
        chat_user_id = user_chats[update.effective_user.id]
        
        # Оптимизация: используем кэш для получения информации о партнере
        # Проверяем active_chat_info для быстрого доступа
        partner = active_chat_info.get(update.effective_user.id)
        
        # Если партнер не в кэше, получаем из БД
        if not partner or partner.id != chat_user_id:
            partner = db.get_user_by_id(chat_user_id)
            if not partner:
                logger.error(f"Собеседник с ID {chat_user_id} не найден в БД")
                await update.message.reply_text(
                    "❌ Ошибка: собеседник не найден. Выйдите из чата и откройте его заново."
                )
                del user_chats[update.effective_user.id]
                active_chat_info.pop(update.effective_user.id, None)
                return
            # Сохраняем в кэш
            active_chat_info[update.effective_user.id] = partner
        
        partner_telegram_id = partner.telegram_id
        
        # Сохраняем сообщение в БД (асинхронно, не блокируем отправку)
        db.add_message(user.id, chat_user_id, text)
        
        # Формируем красивое сообщение для получателя
        gender_emoji = "👨" if user.gender == 'male' else "👩"
        message_text = f"{gender_emoji} {user.name}:\n\n{text}"
        
        # Проверяем, находится ли получатель в чате с отправителем
        # Если нет - добавляем кнопку для перехода в чат
        receiver_in_chat = partner_telegram_id in user_chats and user_chats[partner_telegram_id] == user.id
        reply_markup = None
        
        if not receiver_in_chat:
            # Получатель не в чате с отправителем - добавляем кнопку
            keyboard = [
                [InlineKeyboardButton("💬 Перейти в чат", callback_data=f'open_chat_{user.id}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение собеседнику
        try:
            await context.bot.send_message(
                chat_id=partner_telegram_id,
                text=message_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка при отправке сообщения от {user.telegram_id} к {partner_telegram_id}: {error_msg}")
            
            # Показываем понятное сообщение об ошибке
            if "chat not found" in error_msg.lower() or "user not found" in error_msg.lower() or "bot was blocked" in error_msg.lower():
                await update.message.reply_text(
                    f"❌ Не удалось отправить сообщение.\n"
                    f"Пользователь не найден или заблокировал бота.\n\n"
                    f"Попробуйте выйти из чата и открыть его заново."
                )
            else:
                await update.message.reply_text(
                    f"❌ Не удалось отправить сообщение.\n"
                    f"Попробуйте выйти из чата и открыть его заново."
                )
        return
    else:
        logger.info(f"Пользователь {user.name} НЕ находится в режиме чата. user_chats keys: {list(user_chats.keys())}")
        # Если пользователь не в чате и это не кнопка меню - просто игнорируем или показываем подсказку
        await update.message.reply_text(
            "💡 Вы не находитесь в чате.\n\n"
            "Используйте кнопки меню для навигации или откройте чат через '💬 Мои чаты'."
        )


async def show_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать свою анкету"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    gender_emoji = "👨" if user.gender == 'male' else "👩"
    text = (
        f"👤 Ваша анкета:\n\n"
        f"{gender_emoji} {user.name}, {user.age}\n"
        f"📍 {user.city}\n\n"
        f"{user.description}"
    )
    
    # Для женщин показываем их уникальный код
    if user.gender == 'female' and user.hashtag:
        text += f"\n\n🏷 Ваш уникальный код: {user.hashtag}\nМужчины могут найти вас по этому коду!"
    
    try:
        with open(user.photo_path, 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=text)
    except:
        await update.message.reply_text(text)


async def exit_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выйти из чата"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    chat_partner = None
    
    # Получаем информацию о собеседнике перед выходом
    if update.effective_user.id in user_chats:
        chat_user_id = user_chats[update.effective_user.id]
        chat_partner = db.get_user_by_id(chat_user_id)
        del user_chats[update.effective_user.id]
        if update.effective_user.id in active_chat_info:
            del active_chat_info[update.effective_user.id]
        
        # Уведомляем собеседника, что пользователь покинул чат
        if chat_partner and user:
            try:
                gender_emoji = "👨" if user.gender == 'male' else "👩"
                await context.bot.send_message(
                    chat_id=chat_partner.telegram_id,
                    text=f"🚪 {gender_emoji} {user.name} покинул(а) чат."
                )
                logger.info(f"Уведомление о выходе из чата отправлено {chat_partner.name} (TG: {chat_partner.telegram_id})")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления о выходе из чата {chat_partner.name} (TG: {chat_partner.telegram_id}): {e}")
        
        await update.message.reply_text(
            "🚪 Вы вышли из чата.\n\n"
            "Нажмите '💬 Мои чаты' чтобы выбрать другой чат."
        )
    else:
        await update.message.reply_text("❓ Вы не находитесь в чате.")


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
    
    # Получаем информацию о собеседнике
    partner = db.get_user_by_id(chat_user_id)
    if not partner:
        await update.message.reply_text(
            "❌ Ошибка: собеседник не найден. Выйдите из чата и откройте его заново."
        )
        del user_chats[update.effective_user.id]
        return
    
    # Сохраняем сообщение в БД
    if caption:
        db.add_message(user.id, chat_user_id, f"[Фото] {caption}")
    else:
        db.add_message(user.id, chat_user_id, "[Фото]")
    
    # Проверяем, находится ли получатель в чате с отправителем
    receiver_in_chat = partner.telegram_id in user_chats and user_chats[partner.telegram_id] == user.id
    reply_markup = None
    
    if not receiver_in_chat:
        keyboard = [[InlineKeyboardButton("💬 Перейти в чат", callback_data=f'open_chat_{user.id}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем фото собеседнику
    try:
        gender_emoji = "👨" if user.gender == 'male' else "👩"
        photo_caption = f"📷 {gender_emoji} {user.name}"
        if caption:
            photo_caption += f":\n\n{caption}"
        
        logger.info(f"Отправка фото: от {user.name} (TG: {user.telegram_id}) к {partner.name} (TG: {partner.telegram_id})")
        await context.bot.send_photo(
            chat_id=partner.telegram_id,
            photo=photo.file_id,
            caption=photo_caption,
            reply_markup=reply_markup
        )
        logger.info(f"Фото успешно отправлено от {user.name} к {partner.name}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при отправке фото от {user.name} (TG: {user.telegram_id}) к {partner.name} (TG: {partner.telegram_id}): {e}")
        if "chat not found" in error_msg.lower() or "user not found" in error_msg.lower():
            await update.message.reply_text(
                f"❌ Не удалось отправить фото.\n"
                f"Пользователь не найден или заблокировал бота."
            )
        else:
            await update.message.reply_text(
                f"❌ Не удалось отправить фото.\n"
                f"Ошибка: {error_msg}"
            )
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
    
    # Получаем информацию о собеседнике
    partner = db.get_user_by_id(chat_user_id)
    if not partner:
        await update.message.reply_text(
            "❌ Ошибка: собеседник не найден. Выйдите из чата и откройте его заново."
        )
        del user_chats[update.effective_user.id]
        return
    
    # Сохраняем сообщение в БД
    if caption:
        db.add_message(user.id, chat_user_id, f"[Видео] {caption}")
    else:
        db.add_message(user.id, chat_user_id, "[Видео]")
    
    # Проверяем, находится ли получатель в чате с отправителем
    receiver_in_chat = partner.telegram_id in user_chats and user_chats[partner.telegram_id] == user.id
    reply_markup = None
    
    if not receiver_in_chat:
        keyboard = [[InlineKeyboardButton("💬 Перейти в чат", callback_data=f'open_chat_{user.id}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем видео собеседнику
    try:
        gender_emoji = "👨" if user.gender == 'male' else "👩"
        video_caption = f"🎥 {gender_emoji} {user.name}"
        if caption:
            video_caption += f":\n\n{caption}"
        
        logger.info(f"Отправка видео: от {user.name} (TG: {user.telegram_id}) к {partner.name} (TG: {partner.telegram_id})")
        await context.bot.send_video(
            chat_id=partner.telegram_id,
            video=video.file_id,
            caption=video_caption,
            reply_markup=reply_markup
        )
        logger.info(f"Видео успешно отправлено от {user.name} к {partner.name}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при отправке видео от {user.name} (TG: {user.telegram_id}) к {partner.name} (TG: {partner.telegram_id}): {e}")
        if "chat not found" in error_msg.lower() or "user not found" in error_msg.lower():
            await update.message.reply_text(
                f"❌ Не удалось отправить видео.\n"
                f"Пользователь не найден или заблокировал бота."
            )
        else:
            await update.message.reply_text(
                f"❌ Не удалось отправить видео.\n"
                f"Ошибка: {error_msg}"
            )
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
    
    # Получаем информацию о собеседнике
    partner = db.get_user_by_id(chat_user_id)
    if not partner:
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
    
    # Проверяем, находится ли получатель в чате с отправителем
    receiver_in_chat = partner.telegram_id in user_chats and user_chats[partner.telegram_id] == user.id
    reply_markup = None
    
    if not receiver_in_chat:
        keyboard = [[InlineKeyboardButton("💬 Перейти в чат", callback_data=f'open_chat_{user.id}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем файл собеседнику
    try:
        gender_emoji = "👨" if user.gender == 'male' else "👩"
        doc_caption = f"📎 {gender_emoji} {user.name}"
        if caption:
            doc_caption += f":\n\n{caption}"
        
        logger.info(f"Отправка файла: от {user.name} (TG: {user.telegram_id}) к {partner.name} (TG: {partner.telegram_id})")
        await context.bot.send_document(
            chat_id=partner.telegram_id,
            document=document.file_id,
            caption=doc_caption,
            reply_markup=reply_markup
        )
        logger.info(f"Файл успешно отправлен от {user.name} к {partner.name}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при отправке файла от {user.name} (TG: {user.telegram_id}) к {partner.name} (TG: {partner.telegram_id}): {e}")
        if "chat not found" in error_msg.lower() or "user not found" in error_msg.lower():
            await update.message.reply_text(
                f"❌ Не удалось отправить файл.\n"
                f"Пользователь не найден или заблокировал бота."
            )
        else:
            await update.message.reply_text(
                f"❌ Не удалось отправить файл.\n"
                f"Ошибка: {error_msg}"
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке файла: {e}")
        await update.message.reply_text(
            f"❌ Не удалось отправить файл. Ошибка: {str(e)}"
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена регистрации"""
    await update.message.reply_text("Регистрация отменена.")
    return ConversationHandler.END


# ========== Поиск по хэштэгу ==========

# Словарь для хранения состояния поиска по хэштэгу
hashtag_search_mode = {}


async def start_hashtag_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать поиск по хэштэгу"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    
    if not user:
        await update.message.reply_text("❌ Вы не зарегистрированы. Отправьте /start")
        return
    
    if user.gender != 'male':
        await update.message.reply_text("🔍 Эта функция доступна только для мужчин.")
        return
    
    # Включаем режим поиска по хэштэгу
    hashtag_search_mode[update.effective_user.id] = True
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_hashtag_search')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔍 Поиск по уникальному коду\n\n"
        "Введите код анкеты (например: #ABC1234):\n\n"
        "💡 Девушки могут поделиться своим кодом, "
        "чтобы вы нашли их анкету напрямую.",
        reply_markup=reply_markup
    )


async def process_hashtag_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать введенный хэштэг"""
    user = db.get_user_by_telegram_id(update.effective_user.id)
    hashtag = update.message.text.strip().upper()
    
    # Добавляем # если пользователь не ввел
    if not hashtag.startswith('#'):
        hashtag = '#' + hashtag
    
    # Выходим из режима поиска
    hashtag_search_mode.pop(update.effective_user.id, None)
    
    # Ищем анкету по хэштэгу
    profile = db.get_user_by_hashtag(hashtag)
    
    if not profile:
        await update.message.reply_text(
            f"❌ Анкета с кодом {hashtag} не найдена.\n\n"
            f"Проверьте правильность кода и попробуйте снова."
        )
        return
    
    if profile.gender != 'female':
        await update.message.reply_text("❌ По этому коду анкета не найдена.")
        return
    
    # Проверяем, не лайкнул ли уже
    session = db.get_session()
    try:
        existing_like = session.query(db.Like).filter_by(
            from_user_id=user.id, 
            to_user_id=profile.id
        ).first()
        
        if existing_like:
            if existing_like.chat_started:
                await update.message.reply_text(
                    f"💬 Вы уже начали диалог с {profile.name}!\n"
                    f"Перейдите в '💬 Мои чаты' для общения."
                )
            else:
                await update.message.reply_text(
                    f"❤️ Вы уже отправили симпатию {profile.name}!\n"
                    f"Ожидайте ответа."
                )
            return
    finally:
        session.close()
    
    # Показываем анкету
    text = (
        f"🔍 Найдена анкета по коду {hashtag}:\n\n"
        f"👩 {profile.name}, {profile.age}\n"
        f"📍 {profile.city}\n\n"
        f"{profile.description}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("❤️ Нравится", callback_data=f'like_{profile.id}'),
            InlineKeyboardButton("👎 Пропустить", callback_data=f'dislike_{profile.id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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


async def cancel_hashtag_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена поиска по хэштэгу"""
    query = update.callback_query
    await query.answer()
    
    hashtag_search_mode.pop(update.effective_user.id, None)
    
    await query.edit_message_text("❌ Поиск отменен.")


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
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age_handler)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city_handler)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_handler)],
            PHOTO: [MessageHandler(filters.PHOTO, photo_handler)],
        },
        fallbacks=[
            CommandHandler('start', start),  # Позволяет сбросить регистрацию командой /start
            CommandHandler('cancel', cancel)
        ],
    )
    
    application.add_handler(conv_handler)
    
    # Настройка админ обработчиков
    admin.setup_admin_handlers(application)
    
    # Обработчики callback
    application.add_handler(CallbackQueryHandler(like_callback, pattern='^(like|dislike)_'))
    application.add_handler(CallbackQueryHandler(view_like_callback, pattern='^view_like_'))
    application.add_handler(CallbackQueryHandler(start_chat_callback, pattern='^start_chat_'))
    application.add_handler(CallbackQueryHandler(open_chat_callback, pattern='^open_chat_'))
    application.add_handler(CallbackQueryHandler(exit_chat_callback, pattern='^exit_current_chat$'))
    application.add_handler(CallbackQueryHandler(show_all_chats_callback, pattern='^show_all_chats$'))
    application.add_handler(CallbackQueryHandler(view_partner_callback, pattern='^view_partner_'))
    application.add_handler(CallbackQueryHandler(cancel_hashtag_search_callback, pattern='^cancel_hashtag_search$'))
    
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

