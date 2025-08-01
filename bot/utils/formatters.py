"""
Утилиты для форматирования данных
"""
from datetime import datetime
from typing import Dict, List
from bot.constants import STATUS_ICONS, STATUS_TEXTS


def format_date_for_user(date_str: str) -> str:
    """
    Форматирует дату для пользователя.
    
    Args:
        date_str: Дата в формате YYYY-MM-DD
        
    Returns:
        str: Дата в формате "Понедельник 5 августа"
    """
    if not date_str:
        return "Неизвестная дата"
    
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Русские названия дней недели и месяцев
        weekdays = [
            "Понедельник", "Вторник", "Среда", "Четверг", 
            "Пятница", "Суббота", "Воскресенье"
        ]
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        
        weekday = weekdays[date_obj.weekday()]
        day = date_obj.day
        month = months[date_obj.month - 1]
        
        return f"{weekday} {day} {month}"
    except ValueError:
        return f"Дата: {date_str}"


def format_slot_for_user(slot: Dict) -> str:
    """
    Форматирует слот для отображения пользователю.
    
    Args:
        slot: Словарь с данными слота
        
    Returns:
        str: Отформатированная строка
    """
    date_formatted = format_date_for_user(slot.get("date", ""))
    start_time = slot.get("start_time", "")
    end_time = slot.get("end_time", "")
    location = slot.get("location", "Заповедник")
    
    return f"📅 {date_formatted} с {start_time} до {end_time} • 📍 {location}"


def format_slots_list(slots: List[Dict]) -> str:
    """
    Форматирует список слотов для отображения.
    
    Args:
        slots: Список словарей со слотами
        
    Returns:
        str: Отформатированный список
    """
    if not slots:
        return "Нет доступных слотов"
    
    formatted_slots = []
    for i, slot in enumerate(slots, 1):
        slot_text = format_slot_for_user(slot)
        formatted_slots.append(f"{i}. {slot_text}")
    
    return "\n".join(formatted_slots)


def format_booking_for_user(booking_info: Dict) -> str:
    """
    Форматирует бронирование для отображения клиенту.
    
    Args:
        booking_info: Информация о бронировании
        
    Returns:
        str: Отформатированная строка
    """
    status = booking_info.get("status", "pending")
    status_icon = STATUS_ICONS.get(status, "❓")
    status_text = STATUS_TEXTS.get(status, "Неизвестно")
    
    master_name = booking_info.get("master_name", "Мастер")
    date_formatted = format_date_for_user(booking_info.get("date", ""))
    start_time = booking_info.get("start_time", "")
    end_time = booking_info.get("end_time", "")
    location = booking_info.get("location", "Заповедник")
    
    result = (
        f"{status_icon} **{master_name}**\n"
        f"📅 Время: {date_formatted} с {start_time} до {end_time}\n"
        f"📍 Место: {location}\n"
        f"🔸 Статус: {status_text}"
    )
    
    # Добавляем причину отклонения если есть
    if status == "declined" and booking_info.get("booking", {}).get("decline_reason"):
        reason = booking_info["booking"]["decline_reason"]
        result += f"\n💬 Причина: {reason}"
    
    return result


def format_master_profile(master: Dict) -> str:
    """
    Форматирует профиль мастера для отображения.
    
    Args:
        master: Данные мастера
        
    Returns:
        str: Отформатированный профиль
    """
    name = master.get("name", "Мастер")
    fantasy_description = master.get("fantasy_description", "")
    original_description = master.get("original_description", "")
    services = master.get("services", [])
    slots_count = len(master.get("time_slots", []))
    
    services_text = ", ".join(services) if services else "Не указаны"
    
    return (
        f"👤 **Твой профиль, {name}:**\n\n"
        f"🎭 **Фэнтези-описание:**\n{fantasy_description}\n\n"
        f"📝 **Твои оригинальные слова:**\n{original_description}\n\n"
        f"🛠 **Услуги:** {services_text}\n"
        f"⏰ **Слотов создано:** {slots_count}"
    )


def format_time_range(start_time: str, end_time: str) -> str:
    """
    Форматирует временной диапазон.
    
    Args:
        start_time: Время начала
        end_time: Время окончания
        
    Returns:
        str: Отформатированный диапазон
    """
    return f"{start_time}-{end_time}"


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Обрезает текст до указанной длины.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        
    Returns:
        str: Обрезанный текст
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."