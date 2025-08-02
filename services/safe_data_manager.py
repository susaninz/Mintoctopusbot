#!/usr/bin/env python3
"""
Безопасный менеджер данных с автоматическим резервным копированием
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from .backup_manager import backup_manager

logger = logging.getLogger(__name__)

class SafeDataManager:
    """Безопасный менеджер данных с автоматическим резервным копированием."""
    
    def __init__(self, data_file: str = "data/database.json"):
        self.data_file = data_file
        self.data = None
        self._load_data_safely()
    
    def _load_data_safely(self) -> None:
        """Безопасно загружает данные с проверкой целостности."""
        try:
            # Проверяем целостность текущего файла
            integrity_check = backup_manager.verify_data_integrity(self.data_file)
            
            if not integrity_check['valid']:
                logger.error(f"❌ Основной файл данных поврежден: {integrity_check['error']}")
                self._restore_from_latest_backup()
                return
            
            if not integrity_check['has_critical_data']:
                logger.warning("⚠️ Основной файл не содержит критических данных, проверяем бэкапы...")
                self._restore_from_latest_backup()
                return
            
            # Загружаем данные
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            logger.info(f"✅ Данные загружены успешно: {integrity_check['stats']}")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка загрузки данных: {e}")
            self._restore_from_latest_backup()
    
    def _restore_from_latest_backup(self) -> None:
        """Восстанавливает данные из последнего валидного бэкапа."""
        logger.warning("🔄 Попытка восстановления из резервной копии...")
        
        backups = backup_manager.list_backups()
        
        for backup in backups:
            integrity_check = backup_manager.verify_data_integrity(backup['filepath'])
            
            if integrity_check['valid'] and integrity_check['has_critical_data']:
                logger.info(f"📦 Найден валидный бэкап: {backup['filename']}")
                
                if backup_manager.restore_from_backup(backup['filepath']):
                    with open(self.data_file, 'r', encoding='utf-8') as f:
                        self.data = json.load(f)
                    logger.info("✅ Данные восстановлены из резервной копии")
                    return
        
        # Если не нашли валидных бэкапов, создаем пустую структуру
        logger.error("❌ Не найдено валидных резервных копий, создаем пустую структуру")
        self._create_empty_structure()
    
    def _create_empty_structure(self) -> None:
        """Создает пустую структуру данных."""
        self.data = {
            "masters": [],
            "bookings": [],
            "device_bookings": [],
            "devices": [],
            "locations": [
                {"name": "Баня", "is_open": True},
                {"name": "Спасалка", "is_open": True},
                {"name": "Глэмпинг", "is_open": False}
            ],
            "settings": {
                "max_bookings_per_master": 2,
                "reminder_hours": 1
            },
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_backup": None,
                "version": "1.0"
            }
        }
        self.save_data("emergency_recreate")
        logger.warning("⚠️ Создана пустая структура данных")
    
    def save_data(self, reason: str = "update") -> bool:
        """Безопасно сохраняет данные с созданием резервной копии."""
        try:
            # Создаем резервную копию перед сохранением
            if self.data and reason != "emergency_recreate":
                backup_path = backup_manager.create_timestamped_backup(f"before_{reason}")
                if backup_path:
                    logger.info(f"📦 Создан бэкап перед сохранением: {backup_path}")
            
            # Добавляем метаданные
            if not self.data:
                logger.error("❌ Нет данных для сохранения")
                return False
            
            self.data.setdefault("metadata", {})
            self.data["metadata"]["last_updated"] = datetime.now().isoformat()
            self.data["metadata"]["update_reason"] = reason
            
            # Сохраняем данные
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            # Проверяем целостность сохраненного файла
            integrity_check = backup_manager.verify_data_integrity(self.data_file)
            if not integrity_check['valid']:
                logger.error(f"❌ Сохраненный файл поврежден: {integrity_check['error']}")
                return False
            
            logger.info(f"✅ Данные сохранены успешно (причина: {reason})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")
            return False
    
    def get_data(self) -> Dict[str, Any]:
        """Возвращает текущие данные."""
        if self.data is None:
            self._load_data_safely()
        return self.data
    
    def add_master(self, master_data: Dict) -> bool:
        """Безопасно добавляет мастера."""
        try:
            if not self.data:
                self._load_data_safely()
            
            self.data.setdefault("masters", []).append(master_data)
            return self.save_data("add_master")
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления мастера: {e}")
            return False
    
    def add_booking(self, booking_data: Dict) -> bool:
        """Безопасно добавляет запись."""
        try:
            if not self.data:
                self._load_data_safely()
            
            self.data.setdefault("bookings", []).append(booking_data)
            return self.save_data("add_booking")
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления записи: {e}")
            return False
    
    def add_device_booking(self, device_booking_data: Dict) -> bool:
        """Безопасно добавляет запись на устройство."""
        try:
            if not self.data:
                self._load_data_safely()
            
            self.data.setdefault("device_bookings", []).append(device_booking_data)
            return self.save_data("add_device_booking")
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления записи на устройство: {e}")
            return False
    
    def update_master(self, telegram_id: str, update_data: Dict) -> bool:
        """Безопасно обновляет данные мастера."""
        try:
            if not self.data:
                self._load_data_safely()
            
            masters = self.data.get("masters", [])
            for master in masters:
                if master.get("telegram_id") == telegram_id:
                    master.update(update_data)
                    return self.save_data("update_master")
            
            logger.warning(f"⚠️ Мастер не найден для обновления: {telegram_id}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления мастера: {e}")
            return False
    
    def get_health_status(self) -> Dict:
        """Возвращает статус здоровья системы данных."""
        try:
            integrity_check = backup_manager.verify_data_integrity(self.data_file)
            backups = backup_manager.list_backups()
            recent_backups = [b for b in backups if b['age_hours'] < 24]
            
            return {
                'database_valid': integrity_check['valid'],
                'has_critical_data': integrity_check.get('has_critical_data', False),
                'file_size': integrity_check['stats'].get('file_size', 0),
                'total_backups': len(backups),
                'recent_backups': len(recent_backups),
                'last_backup_age_hours': min([b['age_hours'] for b in backups]) if backups else None,
                'data_stats': integrity_check['stats'],
                'last_updated': self.data.get('metadata', {}).get('last_updated') if self.data else None
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса здоровья: {e}")
            return {'error': str(e)}
    
    def create_manual_backup(self, reason: str = "manual") -> Optional[str]:
        """Создает ручную резервную копию."""
        return backup_manager.create_timestamped_backup(reason)

# Глобальный экземпляр безопасного менеджера данных
safe_data_manager = SafeDataManager()