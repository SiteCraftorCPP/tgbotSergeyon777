"""
Модуль для работы с платежами через ЮKassa
"""
import logging
import uuid
from yookassa import Configuration, Payment
from yookassa.domain.response import PaymentResponse

import config
import database as db

logger = logging.getLogger(__name__)

# Инициализация ЮKassa
def init_yookassa():
    """Инициализация ЮKassa с проверкой настроек"""
    if config.YOOKASSA_SHOP_ID and config.YOOKASSA_SECRET_KEY:
        Configuration.account_id = config.YOOKASSA_SHOP_ID
        Configuration.secret_key = config.YOOKASSA_SECRET_KEY
        logger.info("ЮKassa инициализирована")
    else:
        logger.warning("ЮKassa не настроена: отсутствует SHOP_ID или SECRET_KEY")

# Инициализируем при импорте модуля
init_yookassa()


def create_subscription_payment(user_id: int, telegram_id: int, subscription_type: str) -> dict:
    """
    Создать платёж для подписки
    
    Args:
        user_id: ID пользователя в БД
        telegram_id: Telegram ID пользователя
        subscription_type: 'trial' (1 день) или 'monthly' (месяц)
    
    Returns:
        dict с payment_url и payment_id или error
    """
    try:
        # Проверяем настройки ЮKassa
        if not config.YOOKASSA_SHOP_ID or config.YOOKASSA_SHOP_ID == '0':
            logger.error("YOOKASSA_SHOP_ID не настроен")
            return {
                "success": False,
                "error": "Платёжная система не настроена. Обратитесь к администратору."
            }
        
        if not config.YOOKASSA_SECRET_KEY:
            logger.error("YOOKASSA_SECRET_KEY не настроен")
            return {
                "success": False,
                "error": "Платёжная система не настроена. Обратитесь к администратору."
            }
        
        if subscription_type == 'trial':
            amount = config.SUBSCRIPTION_PRICE_1_DAY
            description = "Premium подписка на 1 день"
        else:
            amount = config.SUBSCRIPTION_PRICE_1_MONTH
            description = "Premium подписка на 1 месяц"
        
        # Создаём платёж в ЮKassa
        # Формируем URL возврата (просто на телеграм, бот сам обработает)
        return_url = "https://t.me"
        
        payment = Payment.create({
            "amount": {
                "value": str(amount) + ".00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": user_id,
                "telegram_id": telegram_id,
                "subscription_type": subscription_type
            }
        }, uuid.uuid4())
        
        # Сохраняем платёж в БД
        db.create_payment(
            user_id=user_id,
            payment_id=payment.id,
            amount=amount * 100,  # Храним в копейках
            payment_type=f'subscription_{subscription_type}',
            description=description
        )
        
        logger.info(f"Создан платёж {payment.id} для пользователя {user_id}, тип: {subscription_type}")
        
        return {
            "success": True,
            "payment_url": payment.confirmation.confirmation_url,
            "payment_id": payment.id
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка создания платежа для пользователя {user_id}: {error_msg}")
        
        # Обрабатываем специфичные ошибки ЮKassa
        if 'invalid_credentials' in error_msg or 'shopId' in error_msg.lower() or 'secret key' in error_msg.lower():
            return {
                "success": False,
                "error": "Ошибка настройки платёжной системы. Проверьте Shop ID и Secret Key в настройках."
            }
        elif 'amount' in error_msg.lower():
            return {
                "success": False,
                "error": "Ошибка суммы платежа. Попробуйте позже."
            }
        else:
            return {
                "success": False,
                "error": f"Ошибка создания платежа: {error_msg}"
            }


def create_donation_payment(amount: int, recipient_user_id: int, donor_telegram_id: int = None) -> dict:
    """
    Создать платёж для доната (отправки денег девушке)
    
    Args:
        amount: Сумма в рублях
        recipient_user_id: ID получателя в БД
        donor_telegram_id: Telegram ID отправителя (если известен)
    
    Returns:
        dict с payment_url и payment_id или error
    """
    try:
        # Проверяем настройки ЮKassa
        if not config.YOOKASSA_SHOP_ID or config.YOOKASSA_SHOP_ID == '0':
            logger.error("YOOKASSA_SHOP_ID не настроен")
            return {
                "success": False,
                "error": "Платёжная система не настроена. Обратитесь к администратору."
            }
        
        if not config.YOOKASSA_SECRET_KEY:
            logger.error("YOOKASSA_SECRET_KEY не настроен")
            return {
                "success": False,
                "error": "Платёжная система не настроена. Обратитесь к администратору."
            }
        
        # Получаем информацию о получателе
        recipient = db.get_user_by_id(recipient_user_id)
        if not recipient:
            return {
                "success": False,
                "error": "Получатель не найден"
            }
        
        description = f"Перевод для {recipient.name}"
        
        # Создаём платёж в ЮKassa
        return_url = "https://t.me"
        
        payment = Payment.create({
            "amount": {
                "value": str(amount) + ".00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": description,
            "metadata": {
                "recipient_user_id": recipient_user_id,
                "donor_telegram_id": donor_telegram_id,
                "payment_type": "donation"
            }
        }, uuid.uuid4())
        
        # Сохраняем платёж в БД
        db.create_payment(
            user_id=None,  # Донор может быть анонимным
            payment_id=payment.id,
            amount=amount * 100,  # Храним в копейках
            payment_type='donation',
            description=description,
            recipient_user_id=recipient_user_id
        )
        
        logger.info(f"Создан донат-платёж {payment.id} для получателя {recipient_user_id}, сумма: {amount}₽")
        
        return {
            "success": True,
            "payment_url": payment.confirmation.confirmation_url,
            "payment_id": payment.id
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка создания доната для получателя {recipient_user_id}: {error_msg}")
        
        # Обрабатываем специфичные ошибки ЮKassa
        if 'invalid_credentials' in error_msg or 'shopId' in error_msg.lower() or 'secret key' in error_msg.lower():
            return {
                "success": False,
                "error": "Ошибка настройки платёжной системы. Проверьте Shop ID и Secret Key в настройках."
            }
        elif 'amount' in error_msg.lower():
            return {
                "success": False,
                "error": "Ошибка суммы платежа. Попробуйте позже."
            }
        else:
            return {
                "success": False,
                "error": f"Ошибка создания платежа: {error_msg}"
            }


def check_payment_status(payment_id: str) -> dict:
    """
    Проверить статус платежа в ЮKassa
    
    Args:
        payment_id: ID платежа в ЮKassa
    
    Returns:
        dict со статусом и метаданными
    """
    try:
        payment = Payment.find_one(payment_id)
        
        return {
            "success": True,
            "status": payment.status,
            "paid": payment.paid,
            "amount": float(payment.amount.value),
            "metadata": payment.metadata
        }
        
    except Exception as e:
        logger.error(f"Ошибка проверки статуса платежа {payment_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def process_successful_payment(payment_id: str) -> bool:
    """
    Обработать успешный платёж
    
    Args:
        payment_id: ID платежа в ЮKassa
    
    Returns:
        True если обработка успешна
    """
    try:
        # Проверяем статус в ЮKassa
        payment_info = check_payment_status(payment_id)
        
        if not payment_info.get('success') or payment_info.get('status') != 'succeeded':
            return False
        
        # Получаем платёж из БД
        db_payment = db.get_payment_by_id(payment_id)
        if not db_payment:
            logger.error(f"Платёж {payment_id} не найден в БД")
            return False
        
        # Если уже обработан
        if db_payment.status == 'succeeded':
            return True
        
        # Обновляем статус
        db.update_payment_status(payment_id, 'succeeded')
        
        metadata = payment_info.get('metadata', {})
        
        # Обрабатываем в зависимости от типа платежа
        if db_payment.payment_type.startswith('subscription_'):
            subscription_type = metadata.get('subscription_type', 'trial')
            user_id = int(metadata.get('user_id'))
            
            # Определяем количество дней
            if subscription_type == 'trial':
                days = 1
            else:
                days = 30
            
            # Создаём подписку
            db.create_subscription(user_id, subscription_type, days)
            logger.info(f"Создана подписка {subscription_type} для пользователя {user_id}")
            
        elif db_payment.payment_type == 'donation':
            # Донат обработан, можно отправить уведомление получателю
            logger.info(f"Донат {payment_id} успешно обработан")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обработки платежа {payment_id}: {e}")
        return False


def generate_donation_link(recipient_user_id: int) -> str:
    """
    Сгенерировать ссылку для доната (пользователь сам укажет сумму в боте)
    
    Args:
        recipient_user_id: ID получателя в БД
    
    Returns:
        Ссылка на бота с параметром для доната
    """
    # Получаем username бота
    try:
        bot_username = config.BOT_TOKEN.split(':')[0]
        # Формируем deep link с ID получателя
        return f"https://t.me/{bot_username}?start=donate_{recipient_user_id}"
    except:
        return None

