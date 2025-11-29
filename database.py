from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index, and_, or_, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config
from functools import lru_cache
import threading

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
        user = User(
            telegram_id=telegram_id,
            username=username,
            name=name,
            gender=gender,
            age=age,
            city=city,
            description=description,
            photo_path=photo_path
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

