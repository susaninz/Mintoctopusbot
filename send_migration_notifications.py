#!/usr/bin/env python3
"""
Скрипт для массовой рассылки уведомлений клиентам о переходе на бота.
Использует готовые персональные сообщения из client_notifications_generated.json
"""

import json
import os
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot

# Загружаем переменные окружения
load_dotenv()

def load_notifications():
    """Загружает готовые уведомления для клиентов."""
    with open('client_notifications_generated.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_database():
    """Загружает базу данных бота для получения telegram_id клиентов."""
    with open('data/database.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def find_user_telegram_id(username, database):
    """Находит telegram_id пользователя по username."""
    # Убираем @ если есть
    clean_username = username.replace('@', '')
    
    # Ищем в мастерах
    for master in database.get('masters', []):
        master_handle = master.get('telegram_handle', '').replace('@', '')
        if master_handle.lower() == clean_username.lower():
            return master.get('telegram_id'), 'master'
    
    # Ищем в бронированиях (клиенты)
    for master in database.get('masters', []):
        for booking in master.get('bookings', []):
            client_username = booking.get('client_username', '').replace('@', '')
            if client_username.lower() == clean_username.lower():
                return booking.get('client_telegram_id'), 'client'
    
    return None, None

async def send_notification(bot, telegram_id, message, username):
    """Отправляет уведомление пользователю."""
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode='Markdown'
        )
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки {username}: {e}")
        return False

async def main():
    """Основная функция рассылки."""
    print("📨 МАССОВАЯ РАССЫЛКА УВЕДОМЛЕНИЙ О МИГРАЦИИ")
    print("=" * 50)
    
    # Загружаем данные
    notifications_data = load_notifications()
    database = load_database()
    notifications = notifications_data.get('notifications', {})
    
    print(f"👥 Всего уведомлений для отправки: {len(notifications)}")
    
    # Инициализируем бота
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token or bot_token == 'your_telegram_bot_token_here':
        print("❌ ОШИБКА: Не установлен BOT_TOKEN в .env файле!")
        return
    
    bot = Bot(token=bot_token)
    
    # Результаты рассылки
    sent_count = 0
    failed_count = 0
    not_found_count = 0
    
    print("\\n🚀 Начинаем рассылку...")
    print("-" * 30)
    
    for username, notification_data in notifications.items():
        print(f"\\n📤 [{sent_count + failed_count + not_found_count + 1}/{len(notifications)}] {username}")
        
        # Ищем telegram_id
        telegram_id, user_type = find_user_telegram_id(username, database)
        
        if not telegram_id:
            print(f"   ⚠️  Telegram ID не найден")
            not_found_count += 1
            continue
        
        print(f"   📋 ID: {telegram_id} (тип: {user_type})")
        message = notification_data.get('message', '')
        
        # Отправляем уведомление
        success = await send_notification(bot, telegram_id, message, username)
        
        if success:
            print(f"   ✅ Отправлено успешно")
            sent_count += 1
        else:
            print(f"   ❌ Не удалось отправить")
            failed_count += 1
        
        # Пауза между отправками (избегаем rate limiting)
        if sent_count + failed_count < len(notifications):
            await asyncio.sleep(1)
    
    print("\\n" + "=" * 50)
    print("📊 ИТОГИ РАССЫЛКИ:")
    print(f"✅ Успешно отправлено: {sent_count}")
    print(f"❌ Ошибки отправки: {failed_count}")
    print(f"⚠️  ID не найдены: {not_found_count}")
    print(f"📝 Всего обработано: {len(notifications)}")
    
    if sent_count > 0:
        print("\\n🎊 Рассылка завершена! Клиенты получили уведомления о переходе на бота.")
    
    # Сохраняем результаты
    results = {
        'timestamp': datetime.now().isoformat(),
        'total_notifications': len(notifications),
        'sent_successfully': sent_count,
        'failed_to_send': failed_count,
        'telegram_id_not_found': not_found_count,
        'sent_to_users': [username for username in notifications.keys()][:sent_count]
    }
    
    with open('migration_broadcast_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\\n💾 Результаты сохранены в migration_broadcast_results.json")

if __name__ == "__main__":
    asyncio.run(main())