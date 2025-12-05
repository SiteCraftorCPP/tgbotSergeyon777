from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index, and_, or_, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config
from functools import lru_cache
import threading
import random
import string

Base = declarative_base()

# Простой кэш для пользователей (TTL не реализован для простоты, но можно добавить)
_user_cache = {}
_cache_lock = threading.Lock()


class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)  # Индекс для быстрого поиска
    username = Column(String(255), nullable=True)
    name = Column(String(100), nullable=False)  # Имя пользователя
    gender = Column(String(10), nullable=False, index=True)  # Индекс для фильтрации по полу
    age = Column(Integer, nullable=False)  # Возраст (просто число)
    city = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    photo_path = Column(String(500), nullable=False)
    hashtag = Column(String(20), unique=True, nullable=True, index=True)  # Уникальный код для женских анкет
    registered_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True, index=True)  # Индекс для фильтрации активных
    
    # Связи
    sent_likes = relationship('Like', foreign_keys='Like.from_user_id', back_populates='from_user')
    received_likes = relationship('Like', foreign_keys='Like.to_user_id', back_populates='to_user')
    sent_messages = relationship('Message', foreign_keys='Message.from_user_id', back_populates='sender')
    received_messages = relationship('Message', foreign_keys='Message.to_user_id', back_populates='receiver')
    
    # Составной индекс для частых запросов
    __table_args__ = (
        Index('idx_gender_active', 'gender', 'is_active'),
        Index('idx_hashtag', 'hashtag'),
    )
    

class Like(Base):
    """Модель лайка/симпатии"""
    __tablename__ = 'likes'
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    to_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)
    is_viewed = Column(Boolean, default=False, index=True)  # Индекс для непросмотренных
    chat_started = Column(Boolean, default=False, index=True)  # Индекс для активных чатов
    
    # Связи
    from_user = relationship('User', foreign_keys=[from_user_id], back_populates='sent_likes')
    to_user = relationship('User', foreign_keys=[to_user_id], back_populates='received_likes')
    
    # Составные индексы для частых запросов
    __table_args__ = (
        Index('idx_to_user_viewed', 'to_user_id', 'is_viewed'),
        Index('idx_from_user_chat', 'from_user_id', 'chat_started'),
        Index('idx_to_user_chat', 'to_user_id', 'chat_started'),
    )


class Message(Base):
    """Модель сообщения в чате"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    to_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now, index=True)  # Индекс для сортировки
    is_read = Column(Boolean, default=False, index=True)  # Индекс для непрочитанных
    
    # Связи
    sender = relationship('User', foreign_keys=[from_user_id], back_populates='sent_messages')
    receiver = relationship('User', foreign_keys=[to_user_id], back_populates='received_messages')
    
    # Составной индекс для частых запросов
    __table_args__ = (
        Index('idx_to_from_read', 'to_user_id', 'from_user_id', 'is_read'),
        Index('idx_users_created', 'from_user_id', 'to_user_id', 'created_at'),
    )


class ViewedProfile(Base):
    """Модель для отслеживания просмотренных анкет"""
    __tablename__ = 'viewed_profiles'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    viewed_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Составной индекс для быстрого поиска
    __table_args__ = (
        Index('idx_user_viewed', 'user_id', 'viewed_user_id'),
    )


class Subscription(Base):
    """Модель подписки пользователя"""
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    subscription_type = Column(String(20), nullable=False)  # 'trial' (1 день) или 'monthly' (месяц)
    started_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Связи
    user = relationship('User', backref='subscriptions')
    
    # Составной индекс для частых запросов
    __table_args__ = (
        Index('idx_user_active_sub', 'user_id', 'is_active'),
    )


class Payment(Base):
    """Модель платежей"""
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)  # Может быть null для донатов
    payment_id = Column(String(100), unique=True, nullable=False, index=True)  # ID платежа в ЮKassa
    amount = Column(Integer, nullable=False)  # Сумма в копейках
    currency = Column(String(10), default='RUB')
    payment_type = Column(String(30), nullable=False)  # 'subscription_trial', 'subscription_monthly', 'donation'
    status = Column(String(30), default='pending')  # pending, succeeded, canceled
    description = Column(String(500), nullable=True)
    recipient_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Для донатов - кому отправлен
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    
    # Связи
    user = relationship('User', foreign_keys=[user_id], backref='payments')
    recipient = relationship('User', foreign_keys=[recipient_user_id])


# Создание движка с оптимизацией для производительности
# Настройки connection pooling для лучшей производительности
pool_config = {
    'pool_size': 10,  # Количество соединений в пуле
    'max_overflow': 20,  # Дополнительные соединения при нагрузке
    'pool_pre_ping': True,  # Проверка соединений перед использованием
    'pool_recycle': 3600,  # Переиспользование соединений каждый час
}

# Для SQLite используем другие настройки
if config.DATABASE_URL.startswith('sqlite'):
    pool_config = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_pre_ping': True,
    }

engine = create_engine(
    config.DATABASE_URL, 
    echo=False,
    **pool_config
)
Session = sessionmaker(bind=engine)


def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(engine)


def get_session():
    """Получить новую сессию БД"""
    return Session()


def generate_unique_hashtag():
    """Генерировать уникальный хэштэг для женской анкеты"""
    session = get_session()
    try:
        while True:
            # Генерируем хэштэг формата: 3 буквы + 4 цифры (например: ABC1234)
            letters = ''.join(random.choices(string.ascii_uppercase, k=3))
            numbers = ''.join(random.choices(string.digits, k=4))
            hashtag = f"#{letters}{numbers}"
            
            # Проверяем уникальность
            existing = session.query(User).filter_by(hashtag=hashtag).first()
            if not existing:
                return hashtag
    finally:
        session.close()


def get_user_by_telegram_id(telegram_id: int):
    """Получить пользователя по Telegram ID (с кэшированием)"""
    # Проверяем кэш
    with _cache_lock:
        if telegram_id in _user_cache:
            return _user_cache[telegram_id]
    
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        # Сохраняем в кэш (только если пользователь найден)
        if user:
            with _cache_lock:
                _user_cache[telegram_id] = user
        return user
    finally:
        session.close()


def invalidate_user_cache(telegram_id: int = None):
    """Очистить кэш пользователя (вызывать после обновления данных)"""
    with _cache_lock:
        if telegram_id:
            _user_cache.pop(telegram_id, None)
        else:
            _user_cache.clear()


def create_user(telegram_id: int, username: str, name: str, gender: str, age: int, 
                city: str, description: str, photo_path: str):
    """Создать нового пользователя"""
    session = get_session()
    try:
        # Генерируем хэштэг только для женских анкет
        hashtag = None
        if gender == 'female':
            hashtag = generate_unique_hashtag()
        
        user = User(
            telegram_id=telegram_id,
            username=username,
            name=name,
            gender=gender,
            age=age,
            city=city,
            description=description,
            photo_path=photo_path,
            hashtag=hashtag
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        # Добавляем в кэш
        with _cache_lock:
            _user_cache[telegram_id] = user
        return user
    finally:
        session.close()


def get_profiles_for_user(user_id: int, city: str, limit: int = 1):
    """Получить анкеты для просмотра (только женские профили для мужчин) - оптимизированная версия"""
    session = get_session()
    try:
        # Оптимизированный запрос: используем подзапросы для исключений
        # Создаем подзапросы для исключенных ID
        viewed_subq = session.query(ViewedProfile.viewed_user_id).filter_by(user_id=user_id).subquery()
        liked_subq = session.query(Like.to_user_id).filter_by(from_user_id=user_id).subquery()
        
        # Объединяем исключенные ID через UNION в подзапросе
        excluded_subq = session.query(viewed_subq.c.viewed_user_id).union(
            session.query(liked_subq.c.to_user_id)
        ).subquery()
        
        # Получаем женские профили с исключением
        query = session.query(User).filter(
            User.gender == 'female',
            User.is_active == True
        )
        
        # Применяем исключение только если есть исключенные ID
        excluded_count = session.query(func.count(excluded_subq.c.viewed_user_id)).scalar()
        if excluded_count > 0:
            query = query.filter(~User.id.in_(session.query(excluded_subq.c.viewed_user_id)))
        
        profiles = query.limit(limit).all()
        return profiles
    except Exception as e:
        # Fallback на упрощенный метод при ошибке
        try:
            viewed_ids = [vid[0] for vid in session.query(ViewedProfile.viewed_user_id).filter_by(user_id=user_id).all()]
            liked_ids = [lid[0] for lid in session.query(Like.to_user_id).filter_by(from_user_id=user_id).all()]
            excluded_ids = list(set(viewed_ids + liked_ids))
            
            query = session.query(User).filter(
                User.gender == 'female',
                User.is_active == True
            )
            if excluded_ids:
                query = query.filter(~User.id.in_(excluded_ids))
            return query.limit(limit).all()
        except:
            return []
    finally:
        session.close()


def add_viewed_profile(user_id: int, viewed_user_id: int):
    """Добавить просмотренную анкету"""
    session = get_session()
    try:
        viewed = ViewedProfile(user_id=user_id, viewed_user_id=viewed_user_id)
        session.add(viewed)
        session.commit()
    finally:
        session.close()


def add_like(from_user_id: int, to_user_id: int):
    """Добавить лайк"""
    session = get_session()
    try:
        like = Like(from_user_id=from_user_id, to_user_id=to_user_id)
        session.add(like)
        session.commit()
        session.refresh(like)
        return like
    finally:
        session.close()


def get_unviewed_likes(user_id: int):
    """Получить непросмотренные лайки для пользователя"""
    session = get_session()
    try:
        likes = session.query(Like).filter_by(
            to_user_id=user_id,
            is_viewed=False
        ).all()
        return likes
    finally:
        session.close()


def mark_like_as_viewed(like_id: int):
    """Отметить лайк как просмотренный"""
    session = get_session()
    try:
        like = session.query(Like).filter_by(id=like_id).first()
        if like:
            like.is_viewed = True
            session.commit()
    finally:
        session.close()


def start_chat(like_id: int):
    """Начать чат (отметить в лайке)"""
    session = get_session()
    try:
        like = session.query(Like).filter_by(id=like_id).first()
        if like:
            like.chat_started = True
            session.commit()
            return True
        return False
    finally:
        session.close()


def add_message(from_user_id: int, to_user_id: int, text: str):
    """Добавить сообщение"""
    session = get_session()
    try:
        message = Message(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            text=text
        )
        session.add(message)
        session.commit()
        return message
    finally:
        session.close()


def get_active_chats(user_id: int):
    """Получить активные чаты пользователя - оптимизированная версия"""
    session = get_session()
    try:
        # Объединяем запросы в один с помощью OR
        likes = session.query(Like).filter(
            or_(
                and_(Like.from_user_id == user_id, Like.chat_started == True),
                and_(Like.to_user_id == user_id, Like.chat_started == True)
            )
        ).all()
        return likes
    finally:
        session.close()


def get_unread_count(user_id: int, from_user_id: int):
    """Получить количество непрочитанных сообщений от конкретного пользователя"""
    session = get_session()
    try:
        count = session.query(Message).filter(
            Message.to_user_id == user_id,
            Message.from_user_id == from_user_id,
            Message.is_read == False
        ).count()
        return count
    finally:
        session.close()


def mark_messages_as_read(user_id: int, from_user_id: int):
    """Отметить все сообщения от пользователя как прочитанные"""
    session = get_session()
    try:
        session.query(Message).filter(
            Message.to_user_id == user_id,
            Message.from_user_id == from_user_id,
            Message.is_read == False
        ).update({Message.is_read: True})
        session.commit()
    finally:
        session.close()


def get_last_message(user1_id: int, user2_id: int):
    """Получить последнее сообщение между двумя пользователями"""
    session = get_session()
    try:
        message = session.query(Message).filter(
            ((Message.from_user_id == user1_id) & (Message.to_user_id == user2_id)) |
            ((Message.from_user_id == user2_id) & (Message.to_user_id == user1_id))
        ).order_by(Message.created_at.desc()).first()
        return message
    finally:
        session.close()


def get_user_by_id(user_id: int):
    """Получить пользователя по ID"""
    session = get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        # Если пользователь найден и есть telegram_id, добавляем в кэш
        if user and user.telegram_id:
            with _cache_lock:
                _user_cache[user.telegram_id] = user
        return user
    finally:
        session.close()


def get_user_by_hashtag(hashtag: str):
    """Получить пользователя по хэштэгу"""
    session = get_session()
    try:
        # Добавляем # если его нет
        if not hashtag.startswith('#'):
            hashtag = '#' + hashtag
        
        user = session.query(User).filter_by(hashtag=hashtag, is_active=True).first()
        return user
    finally:
        session.close()


def get_likes_stats_by_female():
    """Получить статистику лайков по женским анкетам (количество уникальных мужчин, поставивших лайк)"""
    session = get_session()
    try:
        # Получаем все женские анкеты с количеством лайков от разных мужчин
        # В системе один мужчина может поставить только один лайк одной девушке,
        # поэтому count(Like.id) даёт количество уникальных мужчин
        stats = session.query(
            User.id,
            User.name,
            User.age,
            User.hashtag,
            func.count(Like.id).label('likes_count')
        ).outerjoin(
            Like, User.id == Like.to_user_id
        ).filter(
            User.gender == 'female',
            User.is_active == True
        ).group_by(User.id).order_by(func.count(Like.id).desc()).all()
        
        return stats
    finally:
        session.close()


# ========== Функции для работы с подписками ==========

def get_active_subscription(user_id: int):
    """Получить активную подписку пользователя"""
    session = get_session()
    try:
        subscription = session.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.is_active == True,
            Subscription.expires_at > datetime.now()
        ).first()
        return subscription
    finally:
        session.close()


def has_active_subscription(user_id: int) -> bool:
    """Проверить, есть ли у пользователя активная подписка"""
    return get_active_subscription(user_id) is not None


def had_trial_subscription(user_id: int) -> bool:
    """Проверить, была ли у пользователя пробная подписка"""
    session = get_session()
    try:
        trial = session.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.subscription_type == 'trial'
        ).first()
        return trial is not None
    finally:
        session.close()


def create_subscription(user_id: int, subscription_type: str, days: int):
    """Создать подписку для пользователя"""
    from datetime import timedelta
    session = get_session()
    try:
        # Деактивируем старые подписки
        session.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.is_active == True
        ).update({Subscription.is_active: False})
        
        # Создаём новую подписку
        subscription = Subscription(
            user_id=user_id,
            subscription_type=subscription_type,
            started_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=days),
            is_active=True
        )
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        return subscription
    finally:
        session.close()


def get_subscription_info(user_id: int):
    """Получить информацию о подписке пользователя для отображения"""
    session = get_session()
    try:
        subscription = session.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.is_active == True,
            Subscription.expires_at > datetime.now()
        ).first()
        
        if subscription:
            from datetime import timedelta
            remaining = subscription.expires_at - datetime.now()
            days = remaining.days
            hours = remaining.seconds // 3600
            return {
                'active': True,
                'type': subscription.subscription_type,
                'expires_at': subscription.expires_at,
                'days_remaining': days,
                'hours_remaining': hours
            }
        
        # Проверяем, была ли пробная подписка
        had_trial = session.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.subscription_type == 'trial'
        ).first()
        
        return {
            'active': False,
            'had_trial': had_trial is not None
        }
    finally:
        session.close()


# ========== Функции для работы с платежами ==========

def create_payment(user_id: int, payment_id: str, amount: int, payment_type: str, 
                   description: str = None, recipient_user_id: int = None):
    """Создать запись о платеже"""
    session = get_session()
    try:
        payment = Payment(
            user_id=user_id,
            payment_id=payment_id,
            amount=amount,
            payment_type=payment_type,
            description=description,
            recipient_user_id=recipient_user_id,
            status='pending'
        )
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return payment
    finally:
        session.close()


def update_payment_status(payment_id: str, status: str):
    """Обновить статус платежа"""
    session = get_session()
    try:
        payment = session.query(Payment).filter_by(payment_id=payment_id).first()
        if payment:
            payment.status = status
            if status == 'succeeded':
                payment.completed_at = datetime.now()
            session.commit()
            return payment
        return None
    finally:
        session.close()


def get_payment_by_id(payment_id: str):
    """Получить платёж по ID"""
    session = get_session()
    try:
        payment = session.query(Payment).filter_by(payment_id=payment_id).first()
        return payment
    finally:
        session.close()


def get_user_payments(user_id: int, limit: int = 10):
    """Получить последние платежи пользователя"""
    session = get_session()
    try:
        payments = session.query(Payment).filter_by(user_id=user_id).order_by(
            Payment.created_at.desc()
        ).limit(limit).all()
        return payments
    finally:
        session.close()


def get_donations_to_user(recipient_user_id: int):
    """Получить все донаты, отправленные пользователю"""
    session = get_session()
    try:
        donations = session.query(Payment).filter(
            Payment.recipient_user_id == recipient_user_id,
            Payment.payment_type == 'donation',
            Payment.status == 'succeeded'
        ).order_by(Payment.created_at.desc()).all()
        return donations
    finally:
        session.close()


# ========== Функции для редактирования профиля ==========

def update_user_profile(user_id: int, name: str = None, age: int = None, 
                       city: str = None, description: str = None, photo_path: str = None):
    """Обновить профиль пользователя"""
    session = get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False
        
        if name is not None:
            user.name = name
        if age is not None:
            user.age = age
        if city is not None:
            user.city = city
        if description is not None:
            user.description = description
        if photo_path is not None:
            user.photo_path = photo_path
        
        session.commit()
        
        # Обновляем кэш
        if user.telegram_id:
            with _cache_lock:
                _user_cache[user.telegram_id] = user
        
        return True
    finally:
        session.close()


def delete_user_profile(user_id: int):
    """Полностью удалить профиль пользователя (включая связанные данные)"""
    session = get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False
        
        # Удаляем фото
        import os
        try:
            if os.path.exists(user.photo_path):
                os.remove(user.photo_path)
        except:
            pass
        
        # Удаляем связанные данные
        session.query(Like).filter(
            (Like.from_user_id == user_id) | (Like.to_user_id == user_id)
        ).delete()
        
        session.query(Message).filter(
            (Message.from_user_id == user_id) | (Message.to_user_id == user_id)
        ).delete()
        
        session.query(ViewedProfile).filter(
            (ViewedProfile.user_id == user_id) | (ViewedProfile.viewed_user_id == user_id)
        ).delete()
        
        session.query(Subscription).filter_by(user_id=user_id).delete()
        session.query(Payment).filter_by(user_id=user_id).delete()
        
        # Удаляем пользователя
        session.delete(user)
        session.commit()
        
        # Удаляем из кэша
        if user.telegram_id:
            with _cache_lock:
                _user_cache.pop(user.telegram_id, None)
        
        return True
    finally:
        session.close()

