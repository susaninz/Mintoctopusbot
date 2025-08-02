#!/usr/bin/env python3
"""
🚨 КРИТИЧЕСКИЙ HOTFIX
Принудительно перезаписывает database.json с реальными данными
"""

import json
import os
import shutil
from datetime import datetime

def hotfix_database_force():
    """ПРИНУДИТЕЛЬНАЯ перезапись database.json"""
    
    print("🚨 HOTFIX: ПРИНУДИТЕЛЬНАЯ ПЕРЕЗАПИСЬ DATABASE.JSON")
    
    # Реальные данные пользователя
    real_data = {
        "masters": [
            {
                "telegram_id": "494449214",
                "name": "Ваня Слёзкин", 
                "telegram_handle": "@ivanslyozkin",
                "original_description": "С детства любил делать массажи и интуитивно чувствовал как нужно воздействовать. А с 11 лет у меня уже очень сильно болела спина у самого, я прошел сложный период, был продиагностирован компрессионный перелом позвоночника и куча всего. Но, спустя время и путем перебора подходов я на ногах и хочу помогать окружающим справляться с разными состояниями. Учился на Бали, люблю делать массаж по триггерным точкам, имеются аппликатор Кузнецова и Ляпко, аппарат compex для физиотерапии, перкусионный массажер.",
                "services": ["массаж"],
                "time_slots": [],
                "is_active": True,
                "created_at": "2025-08-01T17:10:51.511768",
                "bookings": [],
                "location_preference": "Глэмпинг и Спасалка",
                "fantasy_description": "В таинственных глубинах заповедника, где вековые деревья шепчут тайны здоровья, обитает мастер Ваня Слёзкин. Ещё в ранней юности, он научился слушать песни мышц и искать гармонию в движении, сам преодолев болезненный путь исцеления."
            },
            {
                "telegram_id": "958532944",
                "name": "Коля Богатищев",
                "telegram_handle": "@nik1678", 
                "original_description": "Юмэйхо (японская методика миофасциального массажа)",
                "services": ["массаж"],
                "time_slots": [],
                "is_active": True,
                "created_at": "2025-08-01T17:10:51.511768",
                "bookings": [],
                "location_preference": "Баня",
                "fantasy_description": "Мастер древних практик Коля Богатищев владеет тайным искусством Юмэйхо - японской методикой, которая освобождает мышцы от оков напряжения и возвращает телу утраченную гармонию."
            }
        ],
        "bookings": [],
        "device_bookings": [],
        "devices": [
            {
                "id": "vibro_chair",
                "name": "Виброкресло",
                "owner_telegram_handle": "@fshubin",
                "admin": True,
                "slots": [],
                "bookings": []
            }
        ],
        "stats": {
            "total_masters": 2,
            "total_bookings": 0,
            "total_devices": 1,
            "last_updated": "2025-08-02T14:50:00.000000"
        }
    }
    
    # Пути
    database_path = "/app/data/database.json"
    
    # КРИТИЧНО: Проверяем что volume примонтирован
    if not os.path.exists("/app/data"):
        print("🚨 КРИТИЧЕСКАЯ ОШИБКА: /app/data НЕ СУЩЕСТВУЕТ!")
        print("🔍 Volume НЕ ПРИМОНТИРОВАН или Railway контейнер некорректен")
        print("📋 Список доступных путей в /app:")
        try:
            for item in os.listdir("/app"):
                print(f"  - {item}")
        except:
            print("  ❌ /app недоступен")
        return False
    
    # Проверяем текущее состояние
    if os.path.exists(database_path):
        current_size = os.path.getsize(database_path)
        print(f"🔍 Текущий database.json: {current_size} байт")
        
        # Создаем backup
        backup_path = f"{database_path}.hotfix_backup_{datetime.now().strftime('%H%M%S')}"
        shutil.copy2(database_path, backup_path)
        print(f"💾 Backup создан: {backup_path}")
    else:
        print("❌ database.json НЕ СУЩЕСТВУЕТ в примонтированном volume!")
        print("🔍 Содержимое /app/data:")
        try:
            for item in os.listdir("/app/data"):
                print(f"  - {item}")
        except:
            print("  ❌ /app/data недоступен для чтения")
    
    # ПРИНУДИТЕЛЬНО перезаписываем
    try:
        with open(database_path, 'w', encoding='utf-8') as f:
            json.dump(real_data, f, ensure_ascii=False, indent=2)
        
        new_size = os.path.getsize(database_path)
        print(f"✅ HOTFIX COMPLETED! Новый размер: {new_size} байт")
        
        # Проверяем содержимое
        with open(database_path, 'r', encoding='utf-8') as f:
            check_data = json.load(f)
        
        masters_count = len(check_data.get("masters", []))
        print(f"🔍 Проверка: найдено {masters_count} мастеров")
        
        for master in check_data.get("masters", []):
            print(f"  👤 {master.get('name')} ({master.get('telegram_id')})")
        
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА HOTFIX: {e}")
        return False

if __name__ == "__main__":
    hotfix_database_force()