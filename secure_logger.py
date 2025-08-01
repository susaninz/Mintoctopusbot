"""
Безопасное логирование без секретов
"""
import logging
import re
from typing import Any

class SecureFormatter(logging.Formatter):
    """Форматтер, который скрывает секретные данные"""
    
    # Паттерны для поиска секретов
    SECRET_PATTERNS = [
        # Паттерны для key: value форматов
        (re.compile(r'(token["\'\s]*[:=]["\'\s]*)([a-zA-Z0-9:_-]{10,})'), r'\1***HIDDEN***'),
        (re.compile(r'(api[_-]?key["\'\s]*[:=]["\'\s]*)([a-zA-Z0-9_-]{10,})'), r'\1***HIDDEN***'),
        (re.compile(r'(password["\'\s]*[:=]["\'\s]*)([^\s"\']{8,})'), r'\1***HIDDEN***'),
        (re.compile(r'(secret["\'\s]*[:=]["\'\s]*)([a-zA-Z0-9_-]{10,})'), r'\1***HIDDEN***'),
        
        # Прямые паттерны для токенов
        (re.compile(r'sk-[a-zA-Z0-9]{40,}'), r'sk-***HIDDEN***'),  # OpenAI API keys
        (re.compile(r'bot[0-9]{8,}:[a-zA-Z0-9_-]{35}'), r'bot***HIDDEN***'),  # Telegram bot tokens
        (re.compile(r'[0-9]{8,}:[a-zA-Z0-9_-]{35}'), r'***HIDDEN***'),  # Generic bot tokens
        
        # Общие токены
        (re.compile(r'\b[a-zA-Z0-9]{32,}\b'), r'***HIDDEN***'),  # Generic long tokens
    ]
    
    def format(self, record: logging.LogRecord) -> str:
        # Форматируем сообщение
        formatted = super().format(record)
        
        # Скрываем секреты
        for pattern, replacement in self.SECRET_PATTERNS:
            formatted = pattern.sub(replacement, formatted)
        
        return formatted

def setup_secure_logging(level: str = "INFO") -> None:
    """Настраивает безопасное логирование"""
    # Создаём secure formatter
    formatter = SecureFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Настраиваем консольный handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Настраиваем файловый handler
    file_handler = logging.FileHandler('bot_secure.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Получаем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Очищаем существующие handlers
    root_logger.handlers.clear()
    
    # Добавляем наши handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Отключаем лишние логи от библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

def secure_log_user_action(logger: logging.Logger, user_id: int, action: str, **kwargs) -> None:
    """Безопасно логирует действия пользователей"""
    # Создаём безопасный контекст
    safe_context = {
        key: "***SENSITIVE***" if key in ["password", "token", "secret"] else value
        for key, value in kwargs.items()
    }
    
    logger.info(
        f"User action: user_id={user_id}, action={action}, context={safe_context}"
    )