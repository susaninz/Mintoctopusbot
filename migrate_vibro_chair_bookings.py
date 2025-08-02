#!/usr/bin/env python3
"""
Скрипт миграции записей на виброкресло из таблицы Фила.
Однократное действие для переноса существующих записей в систему бота.
"""

import json
import csv
import uuid
from datetime import datetime

def load_database():
    """Загружает базу данных бота."""
    with open('data/database.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_database(data):
    """Сохраняет базу данных бота."""
    with open('data/database.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_csv_bookings():
    """Парсит CSV файл с записями Фила."""
    bookings = []
    
    with open("Coliving'25 _ Царь-табличка - Вибро кресло.csv", 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Пропускаем заголовок (первая строка)
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
            
        # Парсим формат: "время-время,@username"
        parts = line.split(',')
        if len(parts) >= 2:
            time_range = parts[0].strip()
            username = parts[1].strip()
            
            # Парсим время
            if '-' in time_range:
                start_time, end_time = time_range.split('-')
                start_time = start_time.strip()
                end_time = end_time.strip()
                
                # Добавляем :00 если нет минут
                if ':' not in start_time:
                    start_time += ':00'
                if ':' not in end_time:
                    end_time += ':00'
                
                bookings.append({
                    'date': '2025-08-02',  # 2 августа
                    'start_time': start_time,
                    'end_time': end_time,
                    'username': username
                })
    
    return bookings

def find_device_slot(data, device_id, date, start_time, end_time):
    """Находит конкретный слот устройства."""
    devices = data.get('devices', [])
    
    for device in devices:
        if device['id'] == device_id:
            for i, slot in enumerate(device['time_slots']):
                if (slot['date'] == date and 
                    slot['start_time'] == start_time and 
                    slot['end_time'] == end_time):
                    return i, slot
    
    return None, None

def create_device_booking(data, device_id, slot_index, username, date, start_time, end_time):
    """Создает запись на устройство."""
    booking_id = str(uuid.uuid4())
    
    booking = {
        "booking_id": booking_id,
        "device_id": device_id,
        "slot_index": slot_index,
        "guest_username": username,
        "guest_telegram_id": None,  # Пока неизвестно, пользователь не зарегистрирован
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "status": "confirmed",  # Сразу подтверждаем записи Фила
        "created_at": datetime.now().isoformat(),
        "migrated_from": "phil_table",
        "notes": f"Migrated from Фил's emergency table due to bot downtime"
    }
    
    return booking

def main():
    """Основная функция миграции."""
    print("🚀 Начинаем миграцию записей на виброкресло из таблицы Фила...")
    
    # Загружаем данные
    data = load_database()
    print("✅ База данных загружена")
    
    # Парсим CSV
    bookings_to_migrate = parse_csv_bookings()
    print(f"📋 Найдено {len(bookings_to_migrate)} записей в таблице Фила")
    
    migrated_count = 0
    errors = []
    
    for booking_data in bookings_to_migrate:
        date = booking_data['date']
        start_time = booking_data['start_time']
        end_time = booking_data['end_time']
        username = booking_data['username']
        
        print(f"\n🔍 Обрабатываем запись: {username} на {date} {start_time}-{end_time}")
        
        # Ищем соответствующий слот в виброкресле
        slot_index, slot = find_device_slot(data, 'vibro_chair', date, start_time, end_time)
        
        if slot is None:
            error_msg = f"❌ Слот не найден для {username}: {date} {start_time}-{end_time}"
            print(error_msg)
            errors.append(error_msg)
            continue
        
        # Проверяем, не занят ли уже слот
        if slot.get('is_booked', False):
            error_msg = f"⚠️ Слот уже занят для {username}: {date} {start_time}-{end_time}"
            print(error_msg)
            errors.append(error_msg)
            continue
        
        # Создаем запись
        booking = create_device_booking(
            data, 'vibro_chair', slot_index, username, 
            date, start_time, end_time
        )
        
        # Добавляем в базу данных
        if 'device_bookings' not in data:
            data['device_bookings'] = []
        
        data['device_bookings'].append(booking)
        
        # Помечаем слот как забронированный
        slot['is_booked'] = True
        slot['booked_by'] = username
        slot['booking_id'] = booking['booking_id']
        
        print(f"✅ Создана запись для {username}")
        migrated_count += 1
    
    # Сохраняем изменения
    save_database(data)
    
    print(f"\n🎉 Миграция завершена!")
    print(f"✅ Успешно перенесено записей: {migrated_count}")
    
    if errors:
        print(f"❌ Ошибки ({len(errors)}):")
        for error in errors:
            print(f"   {error}")
    
    print("\n📊 Статистика:")
    print(f"   - Всего записей в таблице Фила: {len(bookings_to_migrate)}")
    print(f"   - Успешно перенесено: {migrated_count}")
    print(f"   - Ошибок: {len(errors)}")
    
    print("\n💡 Пользователи смогут видеть свои записи после регистрации в боте (/start)")

if __name__ == "__main__":
    main()