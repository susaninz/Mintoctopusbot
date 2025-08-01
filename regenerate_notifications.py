#!/usr/bin/env python3
"""
Пересоздание персональных уведомлений только для актуальных клиентов.
"""

import json
from datetime import datetime
from dotenv import load_dotenv
from services.gpt_service import GPTService

load_dotenv()

def load_client_data():
    with open('client_notifications.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_database():
    with open('data/database.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def find_client_bookings(client_username, masters):
    bookings = []
    for master in masters:
        for booking in master.get('bookings', []):
            if (booking.get('client_username') == client_username or 
                booking.get('client_name') == client_username):
                bookings.append({
                    'master_name': booking['master_name'],
                    'date': booking['slot_date'],
                    'time': f"{booking['slot_start_time']}-{booking['slot_end_time']}",
                    'location': booking['location']
                })
    return bookings

def generate_migration_notification(gpt_service, client_username, client_bookings):
    bookings_info = ""
    if client_bookings:
        bookings_info = "\\n\\nТвои записи в заповеднике:\\n"
        for i, booking in enumerate(client_bookings[:3], 1):
            date_formatted = datetime.strptime(booking['date'], '%Y-%m-%d').strftime('%d.%m')
            bookings_info += f"• {booking['master_name']}, {date_formatted} в {booking['time']}, {booking['location']}\\n"
        
        if len(client_bookings) > 3:
            bookings_info += f"• ...и ещё {len(client_bookings) - 3} записей\\n"
    
    prompt = f"""
Ты - дух Мятного Заповедника, волшебного места исцеления и гармонии. 🐙🌊

ЗАДАЧА: Создать персональное уведомление о переходе на нового бота для клиента {client_username}.

КОНТЕКСТ:
• Клиент уже записан на массажи через старую Google табличку
• Теперь вся система переехала в этого бота  
• Нужно объяснить что изменилось и что делать
• Клиент должен понять, что его записи сохранены{bookings_info}

СТРУКТУРА СООБЩЕНИЯ:
1. Приветствие в стиле заповедника
2. Объяснение что система переехала в бота
3. Информация о сохранённых записях (если есть)
4. Преимущества нового бота
5. Простая инструкция что делать
6. Заключение в стиле заповедника

СТИЛЬ НАПИСАНИЯ:
• Мистический, но понятный и дружелюбный
• Используй образы воды, глубин, исцеления, природы
• Добавляй эмодзи океана/мистики: 🐙🌊💫✨🌿
• Тон радостный и заботливый, но не перегруженный
• Макс 5-6 предложений
• Обязательно упомяни username клиента лично

ПРИМЕРЫ МИСТИЧЕСКИХ ФРАЗ:
• "Потоки заповедника принесли весть..."
• "Глубины эволюционировали..."  
• "Мятные течения обновились..."
• "Исцеляющие воды теперь текут через..."
• "Духи заповедника создали новый портал..."

ПРЕИМУЩЕСТВА БОТА (выбери 2-3):
• Автоматические напоминания
• Удобная отмена записей
• История всех массажей
• Прямая связь с мастерами
• Никаких потерянных записей

Создай ПЕРСОНАЛЬНОЕ уведомление прямо сейчас:
"""

    try:
        response = gpt_service.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты - мистический дух Мятного Заповедника, создающий персональные уведомления о переходе на бота."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.8
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Ошибка генерации для {client_username}: {e}")
        
        bookings_text = ""
        if client_bookings:
            first_booking = client_bookings[0]
            date_formatted = datetime.strptime(first_booking['date'], '%Y-%m-%d').strftime('%d.%m')
            bookings_text = f"\\n\\n📅 Твоя ближайшая запись: {first_booking['master_name']}, {date_formatted} в {first_booking['time']}, {first_booking['location']}"
        
        return f"""🐙 Потоки заповедника принесли весть, {client_username}!

Мятные глубины эволюционировали - теперь все массажи бронируются через этого бота! ✨ Твои записи сохранены и ждут тебя.{bookings_text}

🌊 Что нового:
• Автоматические напоминания
• Удобная отмена через бот
• История всех сеансов

Просто нажми /start и окунись в обновлённые воды заповедника! 💫"""

def main():
    print('🔄 ПЕРЕСОЗДАНИЕ УВЕДОМЛЕНИЙ ДЛЯ АКТУАЛЬНЫХ КЛИЕНТОВ')
    print('=' * 60)
    
    client_data = load_client_data()
    database = load_database()
    
    clients = client_data['clients']
    masters = database.get('masters', [])
    
    print(f'👥 Актуальных клиентов: {len(clients)}')
    
    gpt_service = GPTService()
    notifications = {}
    
    for i, client_username in enumerate(clients, 1):
        print(f'\\n🔄 [{i}/{len(clients)}] Генерирую для {client_username}...')
        
        client_bookings = find_client_bookings(client_username, masters)
        
        if client_bookings:
            print(f'   📋 Найдено записей: {len(client_bookings)}')
            for booking in client_bookings:
                date_formatted = datetime.strptime(booking['date'], '%Y-%m-%d').strftime('%d.%m')
                print(f'      • {booking["master_name"]}, {date_formatted} в {booking["time"]}')
        else:
            print(f'   ⚠️ Записи не найдены')
        
        notification = generate_migration_notification(
            gpt_service, 
            client_username, 
            client_bookings
        )
        
        notifications[client_username] = {
            'message': notification,
            'bookings_count': len(client_bookings),
            'generated_at': datetime.now().isoformat()
        }
        
        print(f'   ✅ Сгенерировано ({len(notification)} символов)')
    
    output_data = {
        'notifications': notifications,
        'total_clients': len(clients),
        'generation_date': datetime.now().isoformat(),
        'note': 'Пересоздано после очистки прошедших записей'
    }
    
    with open('client_notifications_generated.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f'\\n💾 Обновлённые уведомления сохранены')
    
    print(f'\\n📋 ПРИМЕРЫ ОБНОВЛЁННЫХ УВЕДОМЛЕНИЙ:')
    print('=' * 50)
    
    for i, (client, data) in enumerate(list(notifications.items())[:2]):
        print(f'\\n👤 {client}:')
        print('─' * 30)
        print(data['message'])
        
        if i < 1:
            print()
    
    if len(notifications) > 2:
        print(f'\\n... и ещё {len(notifications) - 2} уведомлений')
    
    print(f'\\n🎊 ГОТОВО! Обновлённые уведомления для {len(clients)} актуальных клиентов!')

if __name__ == '__main__':
    main()