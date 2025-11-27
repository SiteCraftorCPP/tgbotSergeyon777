#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для очистки базы данных от всех пользователей
"""
import os
import database as db

def clear_all_users():
    """Удалить всех пользователей из БД"""
    session = db.get_session()
    try:
        # Удаляем все связанные данные
        session.query(db.Message).delete()
        session.query(db.Like).delete()
        session.query(db.ViewedProfile).delete()
        session.query(db.User).delete()
        
        session.commit()
        print("✅ Все пользователи и связанные данные удалены из БД")
        print(f"   Удалено записей из таблиц: users, likes, messages, viewed_profiles")
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при очистке БД: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    print("🗑️  Очистка базы данных...")
    clear_all_users()
    print("\n✅ Готово! База данных очищена.")
    print("   Теперь можно пройти регистрацию заново.")

