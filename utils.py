"""
Утилиты для бота Octopus Concierge
"""

from datetime import datetime
from typing import Dict, List

def format_date_for_user(date_str: str) -> str:
    """
    Форматирует дату из ISO формата в удобный для пользователя.
    
    Args:
        date_str: Дата в формате "2025-08-02"
        
    Returns:
        Строка вида "Суббота 2 августа"
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Дни недели на русском
        weekdays = {
            0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
            4: "Пятница", 5: "Суббота", 6: "Воскресенье"
        }
        
        # Месяцы на русском в родительном падеже
        months = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
            7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }
        
        weekday = weekdays[date_obj.weekday()]
        day = date_obj.day
        month = months[date_obj.month]
        
        return f"{weekday} {day} {month}"
        
    except Exception as e:
        # В случае ошибки возвращаем исходную дату
        return date_str

def format_slot_for_user(slot: Dict) -> str:
    """
    Форматирует слот для отображения пользователю.
    
    Args:
        slot: Словарь с данными слота
        
    Returns:
        Строка вида "Суббота 2 августа с 14:00 до 15:00 (баня)"
    """
    date_formatted = format_date_for_user(slot.get("date", ""))
    start_time = slot.get("start_time", "")
    end_time = slot.get("end_time", "")
    location = slot.get("location", "")
    
    return f"{date_formatted} с {start_time} до {end_time} ({location})"

def format_slots_list(slots: List[Dict], show_status: bool = False) -> str:
    """
    Форматирует список слотов для отображения.
    
    Args:
        slots: Список слотов
        show_status: Показывать ли статус слота
        
    Returns:
        Отформатированная строка
    """
    if not slots:
        return "Нет доступных слотов"
    
    formatted_slots = []
    for i, slot in enumerate(slots, 1):
        slot_text = f"{i}. {format_slot_for_user(slot)}"
        
        if show_status:
            status = slot.get("status", "свободен")
            if status == "booked":
                client_name = slot.get("client_name", "клиент")
                slot_text += f" - забронирован ({client_name})"
            else:
                slot_text += " - свободен"
        
        formatted_slots.append(slot_text)
    
    return "\n".join(formatted_slots)