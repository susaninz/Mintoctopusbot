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
        # Данные для восстановления из последних известных рабочих версий
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
    
    # Всегда добавляем bug_reports.json  
    restore_data["bug_reports.json"] = '''
{
  "reports": []
}'''
    
    logger.info("📋 Restoring critical data files...")
    
    for filename, content in restore_data.items():
        file_path = os.path.join(volume_path, filename)
        
        # Если файл не существует или пустой, создаем его
        if not os.path.exists(file_path) or os.path.getsize(file_path) < 100:
            logger.info(f"💾 Creating {filename}")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(json.loads(content), f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Created {filename}")
        else:
            logger.info(f"✅ {filename} already exists and looks good")
    
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