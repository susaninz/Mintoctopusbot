# Utils package

# Реэкспорт функций из корневого utils.py для совместимости
import sys
import os

# Добавляем корневую директорию в path чтобы импортировать utils.py
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    # Импортируем из корневого formatting_utils.py
    import formatting_utils
    
    # Реэкспортируем функции
    format_date_for_user = formatting_utils.format_date_for_user
    format_slot_for_user = formatting_utils.format_slot_for_user
    format_slots_list = formatting_utils.format_slots_list
    
except Exception as e:
    # Fallback на случай ошибки
    def format_date_for_user(date_str: str) -> str:
        return date_str or "Неизвестная дата"
    
    def format_slot_for_user(slot: dict) -> str:
        return f"Слот: {slot.get('date', '')} {slot.get('start_time', '')}"
    
    def format_slots_list(slots: list) -> str:
        return f"Слотов: {len(slots)}"