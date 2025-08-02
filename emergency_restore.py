#!/usr/bin/env python3
"""
EMERGENCY DATA RESTORATION
Восстанавливает данные в volume если они потерялись
"""

import os
import json
import shutil
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def emergency_restore():
    """Восстановление данных в volume"""
    logger.info("🚨 EMERGENCY DATA RESTORATION STARTED")
    
    # Пути
    volume_path = "/app/data"
    local_data_path = "/app/data"
    
    # Проверяем существует ли volume path
    if not os.path.exists(volume_path):
        logger.info(f"📁 Creating volume directory: {volume_path}")
        os.makedirs(volume_path, exist_ok=True)
    
    # Проверяем есть ли локальная копия РЕАЛЬНЫХ данных
    local_database_path = "data/database.json"
    if os.path.exists(local_database_path):
        logger.info(f"📁 Найден локальный database.json, копируем реальные данные...")
        try:
            with open(local_database_path, 'r', encoding='utf-8') as f:
                real_database_content = f.read()
            # Проверяем что это валидный JSON
            json.loads(real_database_content)
            logger.info(f"✅ Локальные данные валидны ({len(real_database_content)} символов)")
            
            # Используем реальные данные
            restore_data = {
                "database.json": real_database_content,
            }
        except Exception as e:
            logger.error(f"❌ Ошибка чтения локальных данных: {e}")
            # Fallback к минимальным данным
            restore_data = {
                "database.json": '''
{
  "masters": [
    {
      "name": "Иван Слёзкин",
      "username": "@ivanslyozkin",
      "profile": "Опытный мастер",
      "slots": []
    }
  ],
  "bookings": [],
  "devices": [
    {
      "name": "Виброкресло",
      "owner": "@fshubin",
      "admin": true,
      "slots": []
    }
  ]
}''',
            }
    else:
        logger.warning("⚠️ Локальный database.json не найден, используем минимальные данные")
        # РЕАЛЬНЫЕ данные для восстановления (компактная версия с основными пользователями)
        restore_data = {
            "database.json": '''{
  "masters": [
    {
      "telegram_id": "494449214",
      "name": "Ваня Слёзкин", 
      "telegram_handle": "@ivanslyozkin",
      "original_description": "С детства любил делать массажи и интуитивно чувствовал как нужно воздействовать. А с 11 лет у меня уже очень сильно болела спина у самого, я прошел сложный период, был продиагностирован компрессионный перелом позвоночника и куча всего. Но, спустя время и путем перебора подходов я на ногах и хочу помогать окружающим справляться с разными состояниями. Учился на Бали, люблю делать массаж по триггерным точкам, имеются аппликатор Кузнецова и Ляпко, аппарат compex для физиотерапии, перкусионный массажер.",
      "services": ["массаж"],
      "time_slots": [],
      "is_active": true,
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
      "is_active": true,
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
      "admin": true,
      "slots": [],
      "bookings": []
    }
  ],
  "stats": {
    "total_masters": 2,
    "total_bookings": 0,
    "total_devices": 1,
    "last_updated": "2025-08-02T13:47:00.000000"
  }
}''',
            }
    
    # Всегда добавляем bug_reports.json  
    restore_data["bug_reports.json"] = '''
{
  "reports": []
}'''
    
    logger.info("📋 Restoring critical data files...")
    
    for filename, content in restore_data.items():
        file_path = os.path.join(volume_path, filename)
        
        # Проверяем нужно ли восстанавливать файл
        needs_restore = False
        
        if not os.path.exists(file_path):
            needs_restore = True
            logger.info(f"💾 {filename} не существует")
        elif filename == "database.json" and os.path.getsize(file_path) < 50000:  # ПРИНУДИТЕЛЬНО для database.json
            needs_restore = True
            current_size = os.path.getsize(file_path)
            logger.info(f"🚨 ПРИНУДИТЕЛЬНАЯ ПЕРЕЗАПИСЬ {filename} ({current_size} байт < 50KB), восстанавливаем РЕАЛЬНЫЕ данные")
        elif os.path.getsize(file_path) < 100:  # Для остальных файлов
            needs_restore = True
            current_size = os.path.getsize(file_path)
            logger.info(f"💾 {filename} слишком мал ({current_size} байт), восстанавливаем")
        
        if needs_restore:
            logger.info(f"🔥 ПРИНУДИТЕЛЬНО ПЕРЕЗАПИСЫВАЕМ {filename}")
            
            # Создаем backup перед перезаписью
            if os.path.exists(file_path):
                backup_path = file_path + f".backup_{datetime.now().strftime('%H%M%S')}"
                import shutil
                shutil.copy2(file_path, backup_path)
                logger.info(f"💾 Backup создан: {backup_path}")
            
            # Перезаписываем файл
            with open(file_path, 'w', encoding='utf-8') as f:
                if isinstance(content, str):
                    # Если content уже строка, парсим и записываем как JSON
                    json.dump(json.loads(content), f, ensure_ascii=False, indent=2)
                else:
                    # Если content уже dict, записываем напрямую
                    json.dump(content, f, ensure_ascii=False, indent=2)
            
            new_size = os.path.getsize(file_path)
            logger.info(f"✅ ПРИНУДИТЕЛЬНО СОЗДАН {filename} ({new_size} байт)")
        else:
            current_size = os.path.getsize(file_path)
            logger.info(f"✅ {filename} already exists and looks good ({current_size} байт)")
    
    # Создаем папку backups
    backups_path = os.path.join(volume_path, "backups")
    if not os.path.exists(backups_path):
        os.makedirs(backups_path, exist_ok=True)
        logger.info(f"📁 Created backups directory: {backups_path}")
    
    # Создаем emergency backup текущего состояния
    backup_filename = f"emergency_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path = os.path.join(backups_path, backup_filename)
    
    # Копируем database.json в backup
    database_path = os.path.join(volume_path, "database.json")
    if os.path.exists(database_path):
        shutil.copy2(database_path, backup_path)
        logger.info(f"💾 Created emergency backup: {backup_filename}")
    
    # Логируем итоговое состояние
    logger.info("📊 Final volume contents:")
    for root, dirs, files in os.walk(volume_path):
        level = root.replace(volume_path, '').count(os.sep)
        indent = ' ' * 2 * level
        logger.info(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            size = os.path.getsize(file_path)
            logger.info(f"{subindent}{file} ({size} bytes)")
    
    logger.info("✅ EMERGENCY DATA RESTORATION COMPLETED")
    return True

if __name__ == "__main__":
    emergency_restore()