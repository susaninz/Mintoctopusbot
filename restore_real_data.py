#!/usr/bin/env python3
"""
RESTORE REAL DATA TO VOLUME
Копирует РЕАЛЬНЫЕ данные из локального database.json в volume
"""

import json
import base64
import requests
import os

def restore_real_data_to_volume():
    """Восстанавливает реальные данные в volume через API"""
    
    # Читаем локальный database.json
    if not os.path.exists("data/database.json"):
        print("❌ Локальный database.json не найден!")
        return False
    
    with open("data/database.json", "r", encoding="utf-8") as f:
        real_data = f.read()
    
    print(f"📊 Локальный database.json: {len(real_data)} символов")
    
    # Кодируем в base64 для безопасной передачи
    encoded_data = base64.b64encode(real_data.encode('utf-8')).decode('ascii')
    
    # Создаем скрипт для выполнения на сервере
    restore_script = f'''
import json
import base64
import os

# Декодируем данные
encoded_data = "{encoded_data}"
real_data = base64.b64decode(encoded_data).decode('utf-8')

# Проверяем что это валидный JSON
try:
    json.loads(real_data)
    print("✅ Данные валидны")
except Exception as e:
    print(f"❌ Невалидные данные: {{e}}")
    exit(1)

# Сохраняем в volume
volume_path = "/app/data/database.json"
try:
    with open(volume_path, 'w', encoding='utf-8') as f:
        f.write(real_data)
    print(f"💾 Данные сохранены в {{volume_path}}")
    
    # Проверяем размер
    size = os.path.getsize(volume_path)
    print(f"📊 Размер файла: {{size}} байт")
    
    # Создаем backup
    backup_path = "/app/data/backups/real_data_restore_backup.json"
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(real_data)
    print(f"💾 Backup создан: {{backup_path}}")
    
except Exception as e:
    print(f"❌ Ошибка сохранения: {{e}}")
    exit(1)

print("✅ РЕАЛЬНЫЕ ДАННЫЕ ВОССТАНОВЛЕНЫ!")
'''
    
    # Сохраняем скрипт
    with open("temp_restore_script.py", "w") as f:
        f.write(restore_script)
    
    print("📝 Скрипт восстановления создан: temp_restore_script.py")
    return True

if __name__ == "__main__":
    restore_real_data_to_volume()