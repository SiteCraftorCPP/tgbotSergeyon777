"""
Админ панель для управления анкетами
"""
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

import config
import database as db

logger = logging.getLogger(__name__)

# Состояния для добавления анкеты админом
ADMIN_NAME, ADMIN_AGE, ADMIN_CITY, ADMIN_DESCRIPTION, ADMIN_PHOTO = range(5)


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id in config.ADMIN_IDS


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать админ меню"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("У вас нет прав доступа к админ панели.")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить женскую анкету", callback_data='admin_add_female')],
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton("👥 Список анкет", callback_data='admin_list_profiles')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔧 Админ панель\n\nВыберите действие:",
        reply_markup=reply_markup
    )


async def admin_add_female_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс добавления женской анкеты"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return ConversationHandler.END
    
    context.user_data['admin_adding'] = True
    context.user_data['gender'] = 'female'
    
    await query.message.reply_text(
        "➕ Добавление женской анкеты\n\n"
        "Укажите имя:"
    )
    return ADMIN_NAME


async def admin_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик имени для админа"""
    name = update.message.text.strip()
    
    if len(name) < 2:
        await update.message.reply_text(
            "❌ Имя слишком короткое. Пожалуйста, укажите имя (минимум 2 символа):"
        )
        return ADMIN_NAME
    
    if len(name) > 100:
        await update.message.reply_text(
            "❌ Имя слишком длинное. Пожалуйста, укажите имя до 100 символов:"
        )
        return ADMIN_NAME
    
    context.user_data['name'] = name
    
    await update.message.reply_text(
        f"Отлично! Укажите возраст (число):"
    )
    return ADMIN_AGE


async def admin_age_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик возраста для админа"""
    age_text = update.message.text.strip()
    
    try:
        age = int(age_text)
        if age < 18 or age > 100:
            await update.message.reply_text(
                "❌ Укажите корректный возраст (18-100):"
            )
            return ADMIN_AGE
    except ValueError:
        await update.message.reply_text(
            "❌ Введите число (например: 22)"
        )
        return ADMIN_AGE
    
    context.user_data['age'] = age
    
    await update.message.reply_text("🏙 Укажите город:")
    return ADMIN_CITY


async def admin_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик города для админа"""
    city = update.message.text.strip()
    context.user_data['city'] = city
    
    await update.message.reply_text(
        "Напишите описание анкеты:"
    )
    return ADMIN_DESCRIPTION


async def admin_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик описания для админа"""
    description = update.message.text.strip()
    context.user_data['description'] = description
    
    await update.message.reply_text("Загрузите фото:")
    return ADMIN_PHOTO


async def admin_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографии для админа"""
    photo = update.message.photo[-1]
    
    # Генерируем уникальный ID для фейковой анкеты
    import random
    fake_telegram_id = random.randint(1000000000, 9999999999)
    
    # Сохраняем фото
    file = await context.bot.get_file(photo.file_id)
    file_path = os.path.join(config.PHOTOS_DIR, f"admin_{fake_telegram_id}.jpg")
    await file.download_to_drive(file_path)
    
    # Создаем пользователя в БД
    user = db.create_user(
        telegram_id=fake_telegram_id,
        username="Анкета от админа",
        name=context.user_data['name'],
        gender='female',
        age=context.user_data['age'],
        city=context.user_data['city'],
        description=context.user_data['description'],
        photo_path=file_path
    )
    
    # Показываем созданную анкету
    text = (
        f"✅ Анкета успешно добавлена!\n\n"
        f"👩 {user.name}, {user.age}\n"
        f"📍 {user.city}\n\n"
        f"{user.description}"
    )
    
    try:
        with open(user.photo_path, 'rb') as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption=text
            )
    except:
        await update.message.reply_text(text)
    
    # Очищаем временные данные
    context.user_data.clear()
    
    return ConversationHandler.END


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    session = db.get_session()
    try:
        total_users = session.query(db.User).count()
        male_users = session.query(db.User).filter_by(gender='male').count()
        female_users = session.query(db.User).filter_by(gender='female').count()
        total_likes = session.query(db.Like).count()
        active_chats = session.query(db.Like).filter_by(chat_started=True).count()
        
        text = (
            f"📊 Статистика бота\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"👨 Мужчин: {male_users}\n"
            f"👩 Женщин: {female_users}\n\n"
            f"❤️ Всего лайков: {total_likes}\n"
            f"💬 Активных чатов: {active_chats}"
        )
        
        await query.message.reply_text(text)
    finally:
        session.close()


async def admin_list_profiles_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех анкет"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    session = db.get_session()
    try:
        # Получаем женские анкеты
        female_profiles = session.query(db.User).filter_by(gender='female').all()
        
        await query.message.reply_text(
            f"👩 Женских анкет в базе: {len(female_profiles)}\n\n"
            f"Отправляю первые 10 анкет..."
        )
        
        # Показываем первые 10 анкет
        for profile in female_profiles[:10]:
            text = (
                f"👩 {profile.name}, {profile.age}\n"
                f"ID: {profile.id}\n"
                f"📍 {profile.city}\n\n"
                f"{profile.description}"
            )
            
            keyboard = [
                [InlineKeyboardButton("🗑 Удалить", callback_data=f'admin_delete_{profile.id}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                with open(profile.photo_path, 'rb') as photo:
                    await query.message.reply_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=reply_markup
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке фото: {e}")
                await query.message.reply_text(text, reply_markup=reply_markup)
    finally:
        session.close()


async def admin_delete_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить анкету"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    profile_id = int(query.data.split('_')[2])
    
    session = db.get_session()
    try:
        profile = session.query(db.User).filter_by(id=profile_id).first()
        if profile:
            # Удаляем фото
            try:
                if os.path.exists(profile.photo_path):
                    os.remove(profile.photo_path)
            except:
                pass
            
            # Помечаем анкету как неактивную вместо удаления
            profile.is_active = False
            session.commit()
            
            await query.edit_message_caption(
                caption=query.message.caption + "\n\n❌ Анкета удалена"
            )
        else:
            await query.message.reply_text("Анкета не найдена.")
    finally:
        session.close()


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена добавления анкеты"""
    context.user_data.clear()
    await update.message.reply_text("Добавление анкеты отменено.")
    return ConversationHandler.END


def setup_admin_handlers(application):
    """Настройка обработчиков админ панели"""
    
    # Обработчик добавления женской анкеты
    admin_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_female_callback, pattern='^admin_add_female$')],
        states={
            ADMIN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_name_handler)],
            ADMIN_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_age_handler)],
            ADMIN_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_city_handler)],
            ADMIN_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_description_handler)],
            ADMIN_PHOTO: [MessageHandler(filters.PHOTO, admin_photo_handler)],
        },
        fallbacks=[CommandHandler('cancel', admin_cancel)],
    )
    
    application.add_handler(CommandHandler('admin', admin_menu))
    application.add_handler(admin_conv_handler)
    application.add_handler(CallbackQueryHandler(admin_stats_callback, pattern='^admin_stats$'))
    application.add_handler(CallbackQueryHandler(admin_list_profiles_callback, pattern='^admin_list_profiles$'))
    application.add_handler(CallbackQueryHandler(admin_delete_profile_callback, pattern='^admin_delete_'))

