"""
Сервис для работы с данными
"""
import json
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from bot.constants import DATABASE_FILE, BACKUP_SUFFIX, DEFAULT_LOCATIONS
from bot.utils.validation import validate_telegram_id

logger = logging.getLogger(__name__)


class DataService:
    """Сервис для работы с JSON базой данных."""
    
    def __init__(self, db_file: str = DATABASE_FILE):
        """
        Инициализация сервиса данных.
        
        Args:
            db_file: Путь к файлу базы данных
        """
        self.db_file = db_file
    
    def load_data(self) -> Dict[str, Any]:
        """
        Загружает данные из JSON файла.
        
        Returns:
            Dict: Данные из базы или пустая структура
        """
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.debug(f"Данные загружены из {self.db_file}")
                    return data
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
        
        # Возвращаем пустую структуру
        logger.info("Создаю новую структуру данных")
        return self._create_empty_structure()
    
    def save_data(self, data: Dict[str, Any]) -> bool:
        """
        Сохраняет данные в JSON файл.
        
        Args:
            data: Данные для сохранения
            
        Returns:
            bool: True если сохранение успешно
        """
        try:
            # Создаем папку если не существует
            os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
            
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Данные сохранены в {self.db_file}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
            return False
    
    def create_backup(self) -> bool:
        """
        Создает резервную копию данных.
        
        Returns:
            bool: True если бэкап создан успешно
        """
        if not os.path.exists(self.db_file):
            return True
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{self.db_file}{BACKUP_SUFFIX}_{timestamp}.json"
        
        try:
            import shutil
            shutil.copy2(self.db_file, backup_file)
            logger.info(f"Создан бэкап: {backup_file}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа: {e}")
            return False
    
    def find_master_by_id(self, telegram_id: str) -> Optional[Dict]:
        """
        Находит мастера по telegram ID.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            Optional[Dict]: Данные мастера или None
        """
        if not validate_telegram_id(telegram_id):
            return None
        
        data = self.load_data()
        masters = data.get("masters", [])
        
        for master in masters:
            if master.get("telegram_id") == telegram_id:
                return master
        
        return None
    
    def find_master_by_handle(self, telegram_handle: str) -> Optional[Dict]:
        """
        Находит мастера по telegram handle.
        
        Args:
            telegram_handle: Handle пользователя (@username)
            
        Returns:
            Optional[Dict]: Данные мастера или None
        """
        if not telegram_handle:
            return None
        
        data = self.load_data()
        masters = data.get("masters", [])
        
        for master in masters:
            if master.get("telegram_handle") == telegram_handle:
                return master
        
        return None
    
    def get_all_masters(self) -> List[Dict]:
        """
        Возвращает список всех активных мастеров.
        
        Returns:
            List[Dict]: Список мастеров
        """
        data = self.load_data()
        masters = data.get("masters", [])
        
        # Возвращаем только активных мастеров
        return [master for master in masters if master.get("is_active", True)]
    
    def add_master(self, master_data: Dict) -> bool:
        """
        Добавляет нового мастера.
        
        Args:
            master_data: Данные мастера
            
        Returns:
            bool: True если мастер добавлен успешно
        """
        data = self.load_data()
        
        # Проверяем, что мастера с таким ID еще нет
        telegram_id = master_data.get("telegram_id")
        if self.find_master_by_id(telegram_id):
            logger.warning(f"Мастер с ID {telegram_id} уже существует")
            return False
        
        # Добавляем временные метки и флаги
        master_data.update({
            "created_at": datetime.now().isoformat(),
            "is_active": True,
            "time_slots": master_data.get("time_slots", []),
            "bookings": master_data.get("bookings", [])
        })
        
        data["masters"].append(master_data)
        return self.save_data(data)
    
    def update_master(self, telegram_id: str, updates: Dict) -> bool:
        """
        Обновляет данные мастера.
        
        Args:
            telegram_id: ID мастера
            updates: Обновления для применения
            
        Returns:
            bool: True если обновление успешно
        """
        data = self.load_data()
        masters = data.get("masters", [])
        
        for master in masters:
            if master.get("telegram_id") == telegram_id:
                master.update(updates)
                master["updated_at"] = datetime.now().isoformat()
                return self.save_data(data)
        
        logger.warning(f"Мастер с ID {telegram_id} не найден для обновления")
        return False
    
    def link_telegram_id(self, telegram_handle: str, telegram_id: str) -> bool:
        """
        Привязывает настоящий telegram_id к профилю мастера.
        
        Args:
            telegram_handle: Handle мастера
            telegram_id: Настоящий ID из Telegram
            
        Returns:
            bool: True если привязка успешна
        """
        data = self.load_data()
        masters = data.get("masters", [])
        
        for master in masters:
            if master.get("telegram_handle") == telegram_handle:
                master["telegram_id"] = telegram_id
                master["verified_at"] = datetime.now().isoformat()
                
                logger.info(f"Привязан ID {telegram_id} к мастеру {master.get('name')} ({telegram_handle})")
                return self.save_data(data)
        
        return False
    
    def _create_empty_structure(self) -> Dict[str, Any]:
        """
        Создает пустую структуру данных.
        
        Returns:
            Dict: Пустая структура базы данных
        """
        return {
            "masters": [],
            "bookings": [],
            "locations": DEFAULT_LOCATIONS.copy(),
            "settings": {
                "max_bookings_per_master": 2,
                "reminder_hours": 1
            }
        }