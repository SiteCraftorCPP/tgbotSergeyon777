from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config

Base = declarative_base()


class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    name = Column(String(100), nullable=False)  # Имя пользователя
    gender = Column(String(10), nullable=False)  # 'male' или 'female'
    birth_date = Column(String(50), nullable=False)
    city = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    photo_path = Column(String(500), nullable=False)
    registered_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    
    # Связи
    sent_likes = relationship('Like', foreign_keys='Like.from_user_id', back_populates='from_user')
    received_likes = relationship('Like', foreign_keys='Like.to_user_id', back_populates='to_user')
    sent_messages = relationship('Message', foreign_keys='Message.from_user_id', back_populates='sender')
    received_messages = relationship('Message', foreign_keys='Message.to_user_id', back_populates='receiver')
    

class Like(Base):
    """Модель лайка/симпатии"""
    __tablename__ = 'likes'
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    to_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    is_viewed = Column(Boolean, default=False)  # Просмотрела ли девушка уведомление
    chat_started = Column(Boolean, default=False)  # Начался ли чат
    
    # Связи
    from_user = relationship('User', foreign_keys=[from_user_id], back_populates='sent_likes')
    to_user = relationship('User', foreign_keys=[to_user_id], back_populates='received_likes')


class Message(Base):
    """Модель сообщения в чате"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    to_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    is_read = Column(Boolean, default=False)
    
    # Связи
    sender = relationship('User', foreign_keys=[from_user_id], back_populates='sent_messages')
    receiver = relationship('User', foreign_keys=[to_user_id], back_populates='received_messages')


class ViewedProfile(Base):
    """Модель для отслеживания просмотренных анкет"""
    __tablename__ = 'viewed_profiles'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    viewed_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)


# Создание движка и сессии
engine = create_engine(config.DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)


def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(engine)


def get_session():
    """Получить новую сессию БД"""
    return Session()


def get_user_by_telegram_id(telegram_id: int):
    """Получить пользователя по Telegram ID"""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        return user
    finally:
        session.close()


def create_user(telegram_id: int, username: str, name: str, gender: str, birth_date: str, 
                city: str, description: str, photo_path: str):
    """Создать нового пользователя"""
    session = get_session()
    try:
        user = User(
            telegram_id=telegram_id,
            username=username,
            name=name,
            gender=gender,
            birth_date=birth_date,
            city=city,
            description=description,
            photo_path=photo_path
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def get_profiles_for_user(user_id: int, city: str, limit: int = 1):
    """Получить анкеты для просмотра (только женские профили для мужчин)"""
    session = get_session()
    try:
        # Получаем ID уже просмотренных анкет
        viewed_ids = session.query(ViewedProfile.viewed_user_id).filter_by(user_id=user_id).all()
        viewed_ids = [vid[0] for vid in viewed_ids]
        
        # Получаем ID анкет, которым уже поставили лайк
        liked_ids = session.query(Like.to_user_id).filter_by(from_user_id=user_id).all()
        liked_ids = [lid[0] for lid in liked_ids]
        
        # Объединяем списки
        excluded_ids = list(set(viewed_ids + liked_ids))
        
        # Получаем женские профили
        query = session.query(User).filter(
            User.gender == 'female',
            User.is_active == True,
            ~User.id.in_(excluded_ids) if excluded_ids else True
        )
        
        profiles = query.limit(limit).all()
        return profiles
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
    """Получить активные чаты пользователя"""
    session = get_session()
    try:
        # Получаем лайки где начат чат
        likes_sent = session.query(Like).filter_by(
            from_user_id=user_id,
            chat_started=True
        ).all()
        
        likes_received = session.query(Like).filter_by(
            to_user_id=user_id,
            chat_started=True
        ).all()
        
        return likes_sent + likes_received
    finally:
        session.close()

