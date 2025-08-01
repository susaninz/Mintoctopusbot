"""
Сервис для работы с мастерами и верификацией
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from bot.services.data_service import DataService
from bot.utils.validation import validate_telegram_id, validate_telegram_handle

logger = logging.getLogger(__name__)


class MasterService:
    """Сервис для управления мастерами и их верификацией."""
    
    def __init__(self, data_service: DataService):
        """
        Инициализация сервиса мастеров.
        
        Args:
            data_service: Сервис для работы с данными
        """
        self.data_service = data_service
    
    def verify_or_create_master(self, user_id: str, username: str = None, user_full_name: str = None) -> tuple[Dict, bool]:
        """
        Верифицирует существующего мастера или предлагает создать нового.
        
        Args:
            user_id: Telegram ID пользователя
            username: Username пользователя (@username)
            user_full_name: Полное имя пользователя
            
        Returns:
            tuple: (master_data или None, is_verified)
        """
        # 1. Ищем по реальному ID (уже привязанные)
        existing_master = self.data_service.find_master_by_id(user_id)
        if existing_master:
            logger.info(f"Мастер найден по ID: {existing_master['name']}")
            return existing_master, True
        
        # 2. Ищем по username (импортированные)
        if username:
            handle = f"@{username}" if not username.startswith("@") else username
            master_by_handle = self.data_service.find_master_by_handle(handle)
            
            if master_by_handle:
                # Привязываем реальный ID
                success = self.data_service.link_telegram_id(handle, user_id)
                if success:
                    logger.info(f"Мастер {master_by_handle['name']} успешно верифицирован по @{username}")
                    return master_by_handle, True
        
        # 3. Ищем по частичному совпадению имени (если есть)
        if user_full_name:
            potential_master = self._find_master_by_name_similarity(user_full_name)
            if potential_master and not potential_master.get("telegram_id", "").isdigit():
                # Это импортированный мастер без корректного ID
                logger.info(f"Найден потенциальный мастер {potential_master['name']} для {user_full_name}")
                return potential_master, False  # Требует подтверждения
        
        # 4. Мастер не найден
        logger.info(f"Мастер не найден для {user_id} (@{username}, {user_full_name})")
        return None, False
    
    def _find_master_by_name_similarity(self, user_full_name: str) -> Optional[Dict]:
        """
        Ищет мастера по частичному совпадению имени.
        
        Args:
            user_full_name: Полное имя пользователя
            
        Returns:
            Optional[Dict]: Найденный мастер или None
        """
        if not user_full_name:
            return None
        
        masters = self.data_service.get_all_masters()
        user_name_lower = user_full_name.lower()
        
        for master in masters:
            master_name = master.get("name", "").lower()
            
            # Проверяем различные варианты совпадений
            if (master_name in user_name_lower or 
                user_name_lower in master_name or
                self._names_match_partially(master_name, user_name_lower)):
                
                return master
        
        return None
    
    def _names_match_partially(self, name1: str, name2: str) -> bool:
        """
        Проверяет частичное совпадение имен.
        
        Args:
            name1: Первое имя
            name2: Второе имя
            
        Returns:
            bool: True если имена частично совпадают
        """
        # Разбиваем на слова и проверяем пересечения
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        # Если есть общие слова длиннее 2 символов
        common_words = words1.intersection(words2)
        return any(len(word) > 2 for word in common_words)
    
    def manually_link_master(self, master_name: str, user_id: str) -> bool:
        """
        Ручная привязка мастера к telegram ID.
        
        Args:
            master_name: Имя мастера из базы
            user_id: Telegram ID пользователя
            
        Returns:
            bool: True если привязка успешна
        """
        masters = self.data_service.get_all_masters()
        
        for master in masters:
            if master.get("name", "").lower() == master_name.lower():
                # Обновляем telegram_id
                updates = {
                    "telegram_id": user_id,
                    "verified_at": datetime.now().isoformat(),
                    "verification_method": "manual"
                }
                
                success = self.data_service.update_master(master.get("telegram_id", ""), updates)
                if success:
                    logger.info(f"Мастер {master_name} вручную привязан к {user_id}")
                    return True
        
        return False
    
    def get_pending_verification_masters(self) -> list:
        """
        Возвращает список мастеров, ожидающих верификации.
        
        Returns:
            list: Мастера с фейковыми ID
        """
        masters = self.data_service.get_all_masters()
        pending = []
        
        for master in masters:
            telegram_id = master.get("telegram_id", "")
            # Если ID не является корректным числом - это фейковый ID
            if not validate_telegram_id(telegram_id):
                pending.append(master)
        
        return pending
    
    def create_new_master_profile(self, user_id: str, username: str = None, user_full_name: str = None) -> Dict:
        """
        Создает профиль для нового мастера.
        
        Args:
            user_id: Telegram ID
            username: Username
            user_full_name: Полное имя
            
        Returns:
            Dict: Данные нового мастера
        """
        handle = f"@{username}" if username and not username.startswith("@") else username
        
        new_master = {
            "telegram_id": user_id,
            "name": user_full_name or f"Мастер {username or user_id[-4:]}",
            "telegram_handle": handle,
            "original_description": "",
            "fantasy_description": "",
            "services": [],
            "time_slots": [],
            "bookings": [],
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "verification_method": "new_registration"
        }
        
        return new_master