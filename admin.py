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
import payments

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
    
    session = db.get_session()
    try:
        male_count = session.query(db.User).filter_by(gender='male', is_active=True).count()
        female_count = session.query(db.User).filter_by(gender='female', is_active=True).count()
    finally:
        session.close()
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить женскую анкету", callback_data='admin_add_female')],
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton("❤️ Статистика лайков", callback_data='admin_likes_stats')],
        [InlineKeyboardButton(f"👥 Список анкет (👨 {male_count} | 👩 {female_count})", callback_data='admin_list_profiles')],
        [InlineKeyboardButton("🔗 Ссылка для оплаты", callback_data='admin_payment_link')]
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
    hashtag_str = user.hashtag if user.hashtag else "—"
    text = (
        f"✅ Анкета успешно добавлена!\n\n"
        f"👩 {user.name}, {user.age}\n"
        f"🏷 Код: {hashtag_str}\n"
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
        
        active_male = session.query(db.User).filter_by(gender='male', is_active=True).count()
        active_female = session.query(db.User).filter_by(gender='female', is_active=True).count()
        
        text = (
            f"📊 Статистика бота\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"   👨 Мужчин: {male_users} (активных: {active_male})\n"
            f"   👩 Женщин: {female_users} (активных: {active_female})"
        )
        
        await query.message.reply_text(text)
    finally:
        session.close()


async def admin_likes_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику лайков по женским анкетам"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    # Получаем статистику лайков
    stats = db.get_likes_stats_by_female()
    
    if not stats:
        await query.message.reply_text(
            "❤️ Статистика лайков\n\n"
            "Пока нет данных о лайках."
        )
        return
    
    # Формируем текст статистики
    text = "❤️ Статистика лайков\n\n"
    
    # Показываем все анкеты, отсортированные по количеству лайков (по убыванию)
    for i, stat in enumerate(stats, 1):
        user_id, name, age, hashtag, likes_count = stat
        hashtag_str = hashtag if hashtag else "—"
        
        text += f"{i}. 👩 {name}, {age}\n"
        text += f"   🏷 Код: {hashtag_str}\n"
        text += f"   ❤️ Лайков: {likes_count}\n\n"
    
    await query.message.reply_text(text)


async def admin_list_profiles_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех анкет для управления"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    keyboard = [
        [InlineKeyboardButton("👩 Все женские анкеты", callback_data='admin_list_female')],
        [InlineKeyboardButton("👨 Все мужские анкеты", callback_data='admin_list_male')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "👥 Управление анкетами\n\n"
        "Выберите категорию:",
        reply_markup=reply_markup
    )


async def admin_list_female_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех женских анкет"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    session = db.get_session()
    try:
        # Получаем все женские анкеты
        profiles = session.query(db.User).filter(
            db.User.gender == 'female',
            db.User.is_active == True
        ).all()
        
        if not profiles:
            await query.message.reply_text(
                "👩 Женские анкеты: 0\n\n"
                "Нет активных женских анкет."
            )
            return
        
        await query.message.reply_text(
            f"👩 Женские анкеты: {len(profiles)}"
        )
        
        # Показываем все анкеты
        for profile in profiles:
            hashtag_str = profile.hashtag if profile.hashtag else "—"
            profile_type = "🤖 Фейк" if profile.username == 'Анкета от админа' else "👤 Реальная"
            text = (
                f"{profile_type}\n"
                f"👩 {profile.name}, {profile.age}\n"
                f"🏷 Код: {hashtag_str}\n"
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


async def admin_list_male_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех мужских анкет"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    session = db.get_session()
    try:
        # Получаем все мужские анкеты
        profiles = session.query(db.User).filter(
            db.User.gender == 'male',
            db.User.is_active == True
        ).all()
        
        if not profiles:
            await query.message.reply_text(
                "👨 Мужские анкеты: 0\n\n"
                "Нет активных мужских анкет."
            )
            return
        
        await query.message.reply_text(
            f"👨 Мужские анкеты: {len(profiles)}"
        )
        
        # Показываем все анкеты
        for profile in profiles:
            text = (
                f"👨 {profile.name}, {profile.age}\n"
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


async def admin_back_to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в админ меню"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    await admin_menu(update, context)


async def admin_delete_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полностью удалить анкету"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    profile_id = int(query.data.split('_')[2])
    
    # Получаем информацию о профиле перед удалением
    profile = db.get_user_by_id(profile_id)
    if not profile:
        await query.message.reply_text("❌ Анкета не найдена.")
        return
    
    profile_name = profile.name
    
    # Полностью удаляем анкету (включая все связанные данные)
    success = db.delete_user_profile(profile_id)
    
    if success:
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n🗑 Анкета полностью удалена из базы данных"
        )
        logger.info(f"Админ {update.effective_user.id} удалил анкету {profile_name} (ID: {profile_id})")
    else:
        await query.message.reply_text("❌ Ошибка при удалении анкеты.")


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена добавления анкеты"""
    context.user_data.clear()
    await update.message.reply_text("Добавление анкеты отменено.")
    return ConversationHandler.END


async def admin_payment_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор анкеты для генерации ссылки на оплату"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    session = db.get_session()
    try:
        # Получаем все женские анкеты (созданные админом)
        female_profiles = session.query(db.User).filter(
            db.User.gender == 'female',
            db.User.is_active == True
        ).all()
        
        if not female_profiles:
            await query.message.reply_text(
                "🔗 Генерация ссылки для оплаты\n\n"
                "❌ Нет доступных анкет."
            )
            return
        
        keyboard = []
        for profile in female_profiles:
            hashtag_str = profile.hashtag if profile.hashtag else "—"
            button_text = f"👩 {profile.name}, {profile.age} ({hashtag_str})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'gen_link_{profile.id}')])
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='admin_cancel_link')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "🔗 Генерация ссылки для оплаты\n\n"
            "Выберите анкету, для которой нужно создать ссылку:\n\n"
            "💡 Эту ссылку можно отправить клиенту, чтобы он сам указал сумму и оплатил.",
            reply_markup=reply_markup
        )
    finally:
        session.close()


async def generate_payment_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сгенерировать ссылку на оплату для выбранной анкеты"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("У вас нет прав доступа.")
        return
    
    profile_id = int(query.data.split('_')[2])
    
    # Получаем информацию о профиле
    profile = db.get_user_by_id(profile_id)
    if not profile:
        await query.message.reply_text("❌ Анкета не найдена.")
        return
    
    # Генерируем ссылку
    # Получаем имя бота из токена или используем заглушку
    try:
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
    except:
        bot_username = "dating_bot"
    
    payment_link = f"https://t.me/{bot_username}?start=donate_{profile_id}"
    
    hashtag_str = profile.hashtag if profile.hashtag else "—"
    
    await query.message.reply_text(
        f"🔗 Ссылка для оплаты\n\n"
        f"👩 Анкета: {profile.name}, {profile.age}\n"
        f"🏷 Код: {hashtag_str}\n\n"
        f"📎 Ссылка для клиента:\n"
        f"`{payment_link}`\n\n"
        f"💡 Отправьте эту ссылку клиенту. Он перейдёт по ней, "
        f"укажет сумму и сможет оплатить.",
        parse_mode='Markdown'
    )


async def admin_cancel_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена генерации ссылки"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Генерация ссылки отменена.")


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
    application.add_handler(CallbackQueryHandler(admin_likes_stats_callback, pattern='^admin_likes_stats$'))
    application.add_handler(CallbackQueryHandler(admin_list_profiles_callback, pattern='^admin_list_profiles$'))
    application.add_handler(CallbackQueryHandler(admin_list_female_callback, pattern='^admin_list_female$'))
    application.add_handler(CallbackQueryHandler(admin_list_male_callback, pattern='^admin_list_male$'))
    application.add_handler(CallbackQueryHandler(admin_back_to_menu_callback, pattern='^admin_back_to_menu$'))
    application.add_handler(CallbackQueryHandler(admin_delete_profile_callback, pattern='^admin_delete_'))
    
    # Обработчики для генерации ссылок на оплату
    application.add_handler(CallbackQueryHandler(admin_payment_link_callback, pattern='^admin_payment_link$'))
    application.add_handler(CallbackQueryHandler(generate_payment_link_callback, pattern='^gen_link_'))
    application.add_handler(CallbackQueryHandler(admin_cancel_link_callback, pattern='^admin_cancel_link$'))

