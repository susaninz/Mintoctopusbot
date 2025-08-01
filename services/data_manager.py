import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional


class DataManager:
    """Управляет сохранением и загрузкой данных в JSON файл."""
    
    def __init__(self, data_file: str = "data/database.json"):
        self.data_file = data_file
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Загружает данные из JSON файла или создает новую структуру."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # Если файл поврежден, создаем новый
                return self._create_empty_structure()
        else:
            # Создаем директорию и файл если их нет
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            return self._create_empty_structure()
    
    def _create_empty_structure(self) -> Dict[str, Any]:
        """Создает пустую структуру данных."""
        return {
            "masters": [],
            "bookings": [],
            "locations": [
                {"name": "Баня", "is_open": True},
                {"name": "Спасалка", "is_open": True},
                {"name": "Глэмпинг", "is_open": False}
            ],
            "settings": {
                "max_bookings_per_master": 2,
                "reminder_hours": 1
            }
        }
    
    def save_data(self) -> None:
        """Сохраняет данные в JSON файл."""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def add_master(self, telegram_id: str, name: str, original_description: str, 
                   fantasy_description: str, services: List[str], time_slots: List[Dict]) -> bool:
        """Добавляет нового мастера."""
        # Проверяем, не существует ли уже мастер с таким telegram_id
        for master in self.data["masters"]:
            if master["telegram_id"] == telegram_id:
                return False  # Мастер уже существует
        
        new_master = {
            "telegram_id": telegram_id,
            "name": name,
            "original_description": original_description,
            "fantasy_description": fantasy_description,
            "services": services,
            "time_slots": time_slots,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }
        
        self.data["masters"].append(new_master)
        self.save_data()
        return True
    
    def get_master_by_telegram_id(self, telegram_id: str) -> Optional[Dict]:
        """Находит мастера по telegram_id."""
        for master in self.data["masters"]:
            if master["telegram_id"] == telegram_id:
                return master
        return None
    
    def get_all_active_masters(self) -> List[Dict]:
        """Возвращает всех активных мастеров."""
        return [master for master in self.data["masters"] if master.get("is_active", True)]
    
    def get_available_slots(self, master_telegram_id: str) -> List[Dict]:
        """Возвращает доступные слоты мастера (не забронированные)."""
        master = self.get_master_by_telegram_id(master_telegram_id)
        if not master:
            return []
        
        # Получаем все забронированные слоты этого мастера
        booked_slots = []
        for booking in self.data["bookings"]:
            if (booking["master_telegram_id"] == master_telegram_id and 
                booking["status"] in ["pending", "confirmed"]):
                booked_slots.append(booking["slot_id"])
        
        # Фильтруем доступные слоты
        available_slots = []
        for i, slot in enumerate(master["time_slots"]):
            slot_id = f"{master_telegram_id}_{i}"
            if slot_id not in booked_slots:
                slot_with_id = slot.copy()
                slot_with_id["slot_id"] = slot_id
                available_slots.append(slot_with_id)
        
        return available_slots
    
    def create_booking(self, guest_telegram_id: str, master_telegram_id: str, 
                      slot_id: str) -> bool:
        """Создает новую запись на сеанс."""
        booking = {
            "booking_id": f"{guest_telegram_id}_{master_telegram_id}_{datetime.now().timestamp()}",
            "guest_telegram_id": guest_telegram_id,
            "master_telegram_id": master_telegram_id,
            "slot_id": slot_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "decline_reason": None
        }
        
        self.data["bookings"].append(booking)
        self.save_data()
        return True
    
    def update_booking_status(self, booking_id: str, status: str, 
                            decline_reason: str = None) -> bool:
        """Обновляет статус записи."""
        for booking in self.data["bookings"]:
            if booking["booking_id"] == booking_id:
                booking["status"] = status
                if decline_reason:
                    booking["decline_reason"] = decline_reason
                booking["updated_at"] = datetime.now().isoformat()
                self.save_data()
                return True
        return False