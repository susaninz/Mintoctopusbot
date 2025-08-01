"""
Утилиты для валидации пользовательского ввода
"""
import re
from typing import Optional
from bot.constants import MAX_USER_INPUT_LENGTH, MIN_TELEGRAM_ID_LENGTH


def validate_telegram_id(user_id: str) -> bool:
    """
    Проверяет корректность telegram ID.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        bool: True если ID корректный
    """
    if not user_id or not isinstance(user_id, str):
        return False
    
    return user_id.isdigit() and len(user_id) >= MIN_TELEGRAM_ID_LENGTH


def sanitize_user_input(text: str) -> str:
    """
    Очищает и ограничивает пользовательский ввод.
    
    Args:
        text: Пользовательский текст
        
    Returns:
        str: Очищенный текст
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Удаляем лишние пробелы и ограничиваем длину
    cleaned = text.strip()[:MAX_USER_INPUT_LENGTH]
    
    # Удаляем потенциально опасные символы
    cleaned = re.sub(r'[<>"\']', '', cleaned)
    
    return cleaned


def validate_telegram_handle(handle: str) -> bool:
    """
    Проверяет корректность telegram handle.
    
    Args:
        handle: Telegram handle (например, @username)
        
    Returns:
        bool: True если handle корректный
    """
    if not handle or not isinstance(handle, str):
        return False
    
    # Должен начинаться с @ и содержать только допустимые символы
    pattern = r'^@[a-zA-Z0-9_]{5,32}$'
    return bool(re.match(pattern, handle))


def validate_time_format(time_str: str) -> bool:
    """
    Проверяет формат времени HH:MM.
    
    Args:
        time_str: Время в формате строки
        
    Returns:
        bool: True если формат корректный
    """
    if not time_str or not isinstance(time_str, str):
        return False
    
    pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
    return bool(re.match(pattern, time_str))


def validate_date_format(date_str: str) -> bool:
    """
    Проверяет формат даты YYYY-MM-DD.
    
    Args:
        date_str: Дата в формате строки
        
    Returns:
        bool: True если формат корректный
    """
    if not date_str or not isinstance(date_str, str):
        return False
    
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    return bool(re.match(pattern, date_str))


def extract_telegram_handle(text: str) -> Optional[str]:
    """
    Извлекает telegram handle из текста.
    
    Args:
        text: Текст для поиска
        
    Returns:
        Optional[str]: Найденный handle или None
    """
    if not text:
        return None
    
    # Ищем паттерн @username
    pattern = r'@[a-zA-Z0-9_]{5,32}'
    match = re.search(pattern, text)
    
    return match.group(0) if match else None