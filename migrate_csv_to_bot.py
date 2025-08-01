#!/usr/bin/env python3
"""
Скрипт миграции данных из CSV таблиц в бота.
Удаляет все существующие слоты и создаёт новые на основе CSV файлов.
"""

import json
import csv
import uuid
from datetime import datetime
from collections import defaultdict

def load_database():
    """Загружает базу данных бота."""
    with open('data/database.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_database(data):
    """Сохраняет базу данных бота."""
    with open('data/database.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def normalize_date(date_str):
    """Нормализует дату из формата DD.MM.YYYY в YYYY-MM-DD."""
    try:
        if '.' in date_str:
            parts = date_str.split('.')
            if len(parts) == 3:
                day, month, year = parts
                if len(year) == 2:
                    year = '20' + year
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except:
        pass
    return None

def normalize_time(time_str):
    """Нормализует время из разных форматов в HH:MM."""
    if not time_str:
        return None
    
    # Убираем пробелы
    time_str = time_str.strip()
    
    # Заменяем дефисы на двоеточия
    time_str = time_str.replace('-', ':')
    
    # Если только час без минут, добавляем :00
    if ':' not in time_str and time_str.isdigit():
        time_str += ':00'
    
    # Проверяем формат HH:MM
    try:
        parts = time_str.split(':')
        if len(parts) == 2:
            hour, minute = parts
            return f"{hour.zfill(2)}:{minute.zfill(2)}"
    except:
        pass
    
    return time_str

def find_master_by_name(masters, master_name):
    """Находит мастера в базе бота по имени."""
    for master in masters:
        if master.get('name', '').lower() == master_name.lower():
            return master
    return None

def create_slot_for_master(master, slot_data):
    """Создаёт слот для мастера."""
    return {
        'date': slot_data['date'],
        'start_time': slot_data['start_time'],
        'end_time': slot_data['end_time'],
        'location': slot_data['location'],
        'is_booked': False
    }

def create_booking_for_master(master, slot_data, client_data):
    """Создаёт бронирование для мастера."""
    booking_id = str(uuid.uuid4())
    
    return {
        'id': booking_id,
        'client_id': 'unknown',  # Будет заполнено при первом контакте с ботом
        'client_name': client_data['display_name'],
        'client_username': client_data['username'],
        'master_id': master['telegram_id'],
        'master_name': master['name'],
        'slot_date': slot_data['date'],
        'slot_start_time': slot_data['start_time'],
        'slot_end_time': slot_data['end_time'],
        'location': slot_data['location'],
        'status': 'confirmed',
        'created_at': datetime.now().isoformat(),
        'migrated_from_csv': True
    }

def normalize_client_name(client_name):
    """Нормализует имя клиента и определяет username."""
    if not client_name or client_name.strip() == '':
        return None
        
    client_name = client_name.strip()
    
    # Исправляем известные случаи
    if client_name.lower() == 'acidrew':
        client_name = '@acidrew'
    
    # Определяем username и display name
    if client_name.startswith('@'):
        return {
            'username': client_name,
            'display_name': client_name
        }
    else:
        return {
            'username': None,
            'display_name': client_name
        }

def main():
    print('🚀 МИГРАЦИЯ CSV ДАННЫХ В БОТА')
    print('=' * 50)
    
    # Загружаем базу данных
    data = load_database()
    masters = data.get('masters', [])
    
    print(f'📊 Мастеров в базе: {len(masters)}')
    
    # Очищаем существующие слоты и бронирования у всех мастеров
    print('🧹 Очищаю существующие слоты и бронирования...')
    for master in masters:
        master['time_slots'] = []
        master['bookings'] = []
    
    # Читаем CSV файл со слотами
    bookings_data = []
    slots_data = defaultdict(list)  # master_name -> [slots]
    
    print('📋 Читаю CSV файл со слотами...')
    
    with open("'25 Мятный Заповедник - Слоты.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # Пропускаем заголовок
        
        for row_num, row in enumerate(reader, 2):
            if len(row) < 6:
                continue
                
            master_name = row[0].strip()
            date_str = row[1].strip()
            location = row[2].strip()
            start_time_str = row[3].strip()
            end_time_str = row[4].strip()
            client_name = row[5].strip()
            
            # Пропускаем пустые строки
            if not master_name or not date_str:
                continue
            
            # Нормализуем дату
            normalized_date = normalize_date(date_str)
            if not normalized_date:
                print(f'⚠️ Строка {row_num}: неверная дата "{date_str}"')
                continue
            
            # Проверяем, что дата в будущем или сегодня
            today = datetime.now().date().strftime('%Y-%m-%d')
            if normalized_date < today:
                print(f'⏭️ Строка {row_num}: пропускаю прошедшую дату {normalized_date}')
                continue
            
            # Нормализуем время
            start_time = normalize_time(start_time_str)
            end_time = normalize_time(end_time_str)
            
            if not start_time or not end_time:
                print(f'⚠️ Строка {row_num}: неверное время "{start_time_str}" - "{end_time_str}"')
                continue
            
            # Создаём данные слота
            slot_data = {
                'date': normalized_date,
                'start_time': start_time,
                'end_time': end_time,
                'location': location or 'Заповедник'
            }
            
            # Добавляем слот к мастеру
            slots_data[master_name].append(slot_data)
            
            # Если есть клиент, создаём бронирование
            if client_name and client_name.strip():
                client_data = normalize_client_name(client_name)
                if client_data:
                    bookings_data.append({
                        'master_name': master_name,
                        'slot_data': slot_data,
                        'client_data': client_data
                    })
                    print(f'📝 Строка {row_num}: {master_name} → {client_data["display_name"]} ({normalized_date} {start_time})')
    
    print(f'\\n📊 Обработано слотов: {sum(len(slots) for slots in slots_data.values())}')
    print(f'📊 Обработано бронирований: {len(bookings_data)}')
    
    # Создаём слоты для мастеров
    print('\\n🎯 Создаю слоты для мастеров...')
    
    for master_name, slots in slots_data.items():
        master = find_master_by_name(masters, master_name)
        if not master:
            print(f'❌ Мастер "{master_name}" не найден в базе бота!')
            continue
        
        # Создаём все слоты (включая занятые)
        for slot_data in slots:
            slot = create_slot_for_master(master, slot_data)
            master['time_slots'].append(slot)
        
        print(f'✅ {master_name}: создано {len(slots)} слотов')
    
    # Создаём бронирования
    print('\\n📋 Создаю бронирования...')
    
    for booking_data in bookings_data:
        master_name = booking_data['master_name']
        master = find_master_by_name(masters, master_name)
        
        if not master:
            continue
        
        booking = create_booking_for_master(
            master, 
            booking_data['slot_data'], 
            booking_data['client_data']
        )
        
        master['bookings'].append(booking)
    
    print(f'✅ Создано {len(bookings_data)} бронирований')
    
    # Сохраняем обновлённую базу
    print('\\n💾 Сохраняю обновлённую базу данных...')
    save_database(data)
    
    print('\\n🎊 МИГРАЦИЯ ЗАВЕРШЕНА!')
    print('\\n📊 ИТОГОВАЯ СТАТИСТИКА:')
    
    for master in masters:
        if master.get('time_slots') or master.get('bookings'):
            name = master.get('name', 'Неизвестно')
            slots_count = len(master.get('time_slots', []))
            bookings_count = len(master.get('bookings', []))
            print(f'• {name}: {slots_count} слотов, {bookings_count} бронирований')
    
    # Создаём список клиентов для рассылки
    print('\\n📱 КЛИЕНТЫ ДЛЯ РАССЫЛКИ:')
    clients_for_notification = set()
    
    for master in masters:
        for booking in master.get('bookings', []):
            if booking.get('client_username'):
                clients_for_notification.add(booking['client_username'])
            elif booking.get('client_name'):
                clients_for_notification.add(booking['client_name'])
    
    print(f'\\n📬 Готово к рассылке: {len(clients_for_notification)} клиентов')
    for client in sorted(clients_for_notification):
        print(f'  • {client}')
    
    # Сохраняем список для рассылки
    notification_data = {
        'clients': list(clients_for_notification),
        'migration_date': datetime.now().isoformat(),
        'total_bookings': len(bookings_data)
    }
    
    with open('client_notifications.json', 'w', encoding='utf-8') as f:
        json.dump(notification_data, f, ensure_ascii=False, indent=2)
    
    print(f'\\n📄 Данные для рассылки сохранены в client_notifications.json')

if __name__ == '__main__':
    main()