"""
Утилиты для работы с московским временем
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional

# Московский часовой пояс (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

def moscow_now() -> datetime:
    """Возвращает текущее время в московском часовом поясе"""
    return datetime.now(MOSCOW_TZ)

def moscow_today() -> date:
    """Возвращает сегодняшнюю дату по московскому времени"""
    return moscow_now().date()

def moscow_tomorrow() -> date:
    """Возвращает завтрашнюю дату по московскому времени"""
    return moscow_today() + timedelta(days=1)

def moscow_date_str(days_offset: int = 0) -> str:
    """
    Возвращает дату в формате YYYY-MM-DD по московскому времени
    
    Args:
        days_offset: Смещение в днях от сегодня (0 = сегодня, 1 = завтра, -1 = вчера)
    """
    target_date = moscow_today() + timedelta(days=days_offset)
    return target_date.strftime('%Y-%m-%d')

def moscow_time_str() -> str:
    """Возвращает текущее время в формате HH:MM по московскому времени"""
    return moscow_now().strftime('%H:%M')

def moscow_datetime_str() -> str:
    """Возвращает текущую дату и время в ISO формате по московскому времени"""
    return moscow_now().isoformat()

def is_past_slot(slot_date: str, slot_time: str) -> bool:
    """
    Проверяет, прошел ли слот по московскому времени
    
    Args:
        slot_date: Дата в формате YYYY-MM-DD
        slot_time: Время в формате HH:MM
        
    Returns:
        True если слот уже прошел
    """
    try:
        # Парсим дату и время слота
        slot_datetime_naive = datetime.strptime(f"{slot_date} {slot_time}", "%Y-%m-%d %H:%M")
        
        # Добавляем московский часовой пояс к слоту
        slot_datetime_moscow = slot_datetime_naive.replace(tzinfo=MOSCOW_TZ)
        
        # Сравниваем с текущим московским временем
        return slot_datetime_moscow <= moscow_now()
        
    except (ValueError, TypeError):
        # Если не удалось распарсить, считаем что слот прошел (безопасное поведение)
        return True

def get_relative_date_info() -> dict:
    """
    Возвращает информацию об относительных датах для GPT
    """
    moscow_time = moscow_now()
    
    return {
        "current_moscow_time": moscow_time.strftime("%Y-%m-%d %H:%M"),
        "current_date": moscow_today().strftime("%Y-%m-%d"),
        "tomorrow_date": moscow_tomorrow().strftime("%Y-%m-%d"),
        "current_weekday": moscow_time.strftime("%A"),
        "current_hour": moscow_time.hour,
        "timezone": "Europe/Moscow"
    }

def parse_relative_date(relative_text: str, reference_time: Optional[datetime] = None) -> Optional[str]:
    """
    Парсит относительные даты типа "завтра", "сегодня" с учетом московского времени
    
    Args:
        relative_text: Текст типа "завтра", "сегодня", "послезавтра"
        reference_time: Опорное время (по умолчанию - текущее московское)
        
    Returns:
        Дата в формате YYYY-MM-DD или None если не удалось распарсить
    """
    if not reference_time:
        reference_time = moscow_now()
    elif reference_time.tzinfo is None:
        # Если время без часового пояса, считаем что это московское время
        reference_time = reference_time.replace(tzinfo=MOSCOW_TZ)
    
    reference_date = reference_time.date()
    relative_text_lower = relative_text.lower().strip()
    
    if relative_text_lower in ["сегодня", "today"]:
        return reference_date.strftime("%Y-%m-%d")
    elif relative_text_lower in ["завтра", "tomorrow"]:
        return (reference_date + timedelta(days=1)).strftime("%Y-%m-%d")
    elif relative_text_lower in ["послезавтра", "day after tomorrow"]:
        return (reference_date + timedelta(days=2)).strftime("%Y-%m-%d")
    elif relative_text_lower in ["вчера", "yesterday"]:
        return (reference_date - timedelta(days=1)).strftime("%Y-%m-%d")
    
    return None

def format_moscow_time_for_user(dt: Optional[datetime] = None) -> str:
    """
    Форматирует время для показа пользователю в московском часовом поясе
    
    Args:
        dt: datetime объект (если None, используется текущее время)
        
    Returns:
        Строка в формате "2025-08-01 15:30 МСК"
    """
    if dt is None:
        dt = moscow_now()
    elif dt.tzinfo is None:
        # Если время без часового пояса, добавляем московский часовой пояс
        dt = dt.replace(tzinfo=MOSCOW_TZ)
    elif dt.tzinfo != MOSCOW_TZ:
        # Если время в другом часовом поясе, конвертируем в московское
        dt = dt.astimezone(MOSCOW_TZ)
    
    return dt.strftime("%Y-%m-%d %H:%M МСК")

# Для обратной совместимости - функции-алиасы
def get_moscow_now():
    """Алиас для moscow_now()"""
    return moscow_now()

def get_moscow_today():
    """Алиас для moscow_today()"""  
    return moscow_today()

def format_date_for_notification(date_str: str) -> str:
    """
    Форматирует дату для уведомлений в формате "2 августа (суббота)"
    
    Args:
        date_str: Дата в формате YYYY-MM-DD
        
    Returns:
        Строка в формате "день месяц (день недели)"
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Названия месяцев на русском
        month_names = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля", 
            5: "мая", 6: "июня", 7: "июля", 8: "августа",
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }
        
        # Названия дней недели на русском
        weekday_names = {
            0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
            4: "пятница", 5: "суббота", 6: "воскресенье"
        }
        
        day = date_obj.day
        month = month_names[date_obj.month]
        weekday = weekday_names[date_obj.weekday()]
        
        return f"{day} {month} ({weekday})"
        
    except (ValueError, KeyError):
        # Если не удалось распарсить, возвращаем оригинальную строку
        return date_str