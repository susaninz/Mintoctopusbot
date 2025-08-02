#!/usr/bin/env python3
"""
Менеджер резервного копирования и защиты данных пользователей
"""

import json
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class BackupManager:
    """Управляет резервным копированием и версионированием данных."""
    
    def __init__(self, data_file: str = "data/database.json", backup_dir: str = "data/backups"):
        self.data_file = data_file
        self.backup_dir = backup_dir
        self.ensure_backup_dir()
    
    def ensure_backup_dir(self):
        """Создает папку для резервных копий."""
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_timestamped_backup(self, reason: str = "manual") -> str:
        """Создает резервную копию с временной меткой."""
        if not os.path.exists(self.data_file):
            logger.warning(f"Основной файл данных не найден: {self.data_file}")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"database_backup_{timestamp}_{reason}.json"
        backup_path = os.path.join(self.backup_dir, backup_filename)
        
        try:
            shutil.copy2(self.data_file, backup_path)
            logger.info(f"✅ Создана резервная копия: {backup_path}")
            
            # Логируем статистику данных в бэкапе
            self._log_backup_stats(backup_path, reason)
            
            return backup_path
        except Exception as e:
            logger.error(f"❌ Ошибка создания резервной копии: {e}")
            return None
    
    def _log_backup_stats(self, backup_path: str, reason: str):
        """Логирует статистику сохраненных данных."""
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            masters_count = len(data.get("masters", []))
            bookings_count = len(data.get("bookings", []))
            device_bookings_count = len(data.get("device_bookings", []))
            devices_count = len(data.get("devices", []))
            
            logger.info(f"📊 Статистика бэкапа ({reason}):")
            logger.info(f"   - Мастеров: {masters_count}")
            logger.info(f"   - Записей на мастеров: {bookings_count}")
            logger.info(f"   - Записей на устройства: {device_bookings_count}")
            logger.info(f"   - Устройств: {devices_count}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа статистики бэкапа: {e}")
    
    def create_pre_deployment_backup(self) -> str:
        """Создает резервную копию перед деплоем."""
        return self.create_timestamped_backup("pre_deploy")
    
    def create_pre_migration_backup(self) -> str:
        """Создает резервную копию перед миграцией."""
        return self.create_timestamped_backup("pre_migration")
    
    def list_backups(self) -> List[Dict]:
        """Возвращает список всех резервных копий."""
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for filename in os.listdir(self.backup_dir):
            if filename.endswith('.json') and 'backup' in filename:
                filepath = os.path.join(self.backup_dir, filename)
                try:
                    stat = os.stat(filepath)
                    backups.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size': stat.st_size,
                        'created': datetime.fromtimestamp(stat.st_mtime),
                        'age_hours': (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).total_seconds() / 3600
                    })
                except Exception as e:
                    logger.error(f"Ошибка чтения информации о бэкапе {filename}: {e}")
        
        # Сортируем по дате создания (новые первые)
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups
    
    def restore_from_backup(self, backup_path: str) -> bool:
        """Восстанавливает данные из резервной копии."""
        if not os.path.exists(backup_path):
            logger.error(f"❌ Резервная копия не найдена: {backup_path}")
            return False
        
        try:
            # Проверяем валидность бэкапа
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Создаем резервную копию текущих данных перед восстановлением
            current_backup = self.create_timestamped_backup("before_restore")
            
            # Восстанавливаем данные
            shutil.copy2(backup_path, self.data_file)
            
            logger.info(f"✅ Данные восстановлены из: {backup_path}")
            logger.info(f"📦 Текущие данные сохранены в: {current_backup}")
            
            self._log_backup_stats(backup_path, "restore")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления из резервной копии: {e}")
            return False
    
    def cleanup_old_backups(self, keep_days: int = 7) -> int:
        """Удаляет старые резервные копии (старше указанного количества дней)."""
        if keep_days <= 0:
            logger.warning("⚠️ Автоматическая очистка отключена (keep_days <= 0)")
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        removed_count = 0
        
        backups = self.list_backups()
        for backup in backups:
            if backup['created'] < cutoff_date:
                try:
                    os.remove(backup['filepath'])
                    logger.info(f"🗑️ Удален старый бэкап: {backup['filename']}")
                    removed_count += 1
                except Exception as e:
                    logger.error(f"❌ Ошибка удаления бэкапа {backup['filename']}: {e}")
        
        logger.info(f"📦 Очистка завершена: удалено {removed_count} старых бэкапов")
        return removed_count
    
    def verify_data_integrity(self, filepath: str = None) -> Dict:
        """Проверяет целостность данных в файле."""
        target_file = filepath or self.data_file
        
        if not os.path.exists(target_file):
            return {
                'valid': False,
                'error': f'Файл не найден: {target_file}',
                'stats': {}
            }
        
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Проверяем обязательные разделы
            required_sections = ['masters', 'bookings', 'devices', 'device_bookings']
            missing_sections = [section for section in required_sections if section not in data]
            
            # Собираем статистику
            stats = {
                'masters': len(data.get('masters', [])),
                'bookings': len(data.get('bookings', [])),
                'device_bookings': len(data.get('device_bookings', [])),
                'devices': len(data.get('devices', [])),
                'file_size': os.path.getsize(target_file),
                'missing_sections': missing_sections
            }
            
            # Проверяем критические данные
            has_critical_data = (
                stats['masters'] > 0 or 
                stats['bookings'] > 0 or 
                stats['device_bookings'] > 0
            )
            
            return {
                'valid': len(missing_sections) == 0,
                'has_critical_data': has_critical_data,
                'error': f'Отсутствуют разделы: {missing_sections}' if missing_sections else None,
                'stats': stats
            }
            
        except json.JSONDecodeError as e:
            return {
                'valid': False,
                'error': f'Невалидный JSON: {e}',
                'stats': {}
            }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Ошибка чтения файла: {e}',
                'stats': {}
            }

# Глобальный экземпляр менеджера
backup_manager = BackupManager()