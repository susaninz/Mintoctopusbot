"""
Middleware для обработки ошибок и rate limiting
"""
import asyncio
import time
from functools import wraps
from typing import Dict, Optional
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import RetryAfter, TimedOut, NetworkError

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter для предотвращения спама"""
    
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}
    
    def is_allowed(self, user_id: str) -> bool:
        """Проверяет, разрешён ли запрос от пользователя"""
        now = time.time()
        
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        # Очищаем старые запросы
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if now - req_time < self.window_seconds
        ]
        
        # Проверяем лимит
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        # Добавляем текущий запрос
        self.requests[user_id].append(now)
        return True

# Глобальный rate limiter
rate_limiter = RateLimiter()

def with_error_handling(func):
    """Декоратор для обработки ошибок в хендлерах"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except RetryAfter as e:
            logger.warning(f"Rate limited, retry after {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
            return await func(update, context, *args, **kwargs)
        except (TimedOut, NetworkError) as e:
            logger.error(f"Network error in {func.__name__}: {e}")
            if update.message:
                try:
                    await update.message.reply_text(
                        "🌊 Течения заповедника временно нестабильны. Попробуй ещё раз через мгновение..."
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            if update.message:
                try:
                    await update.message.reply_text(
                        "🐙 Что-то пошло не так в глубинах заповедника. Администрация уже знает об этом!"
                    )
                except Exception:
                    pass
    return wrapper

def with_rate_limiting(func):
    """Декоратор для rate limiting"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id)
        
        if not rate_limiter.is_allowed(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            if update.message:
                await update.message.reply_text(
                    "🌊 Потоки заповедника перегружены. Немного подожди перед следующим запросом..."
                )
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper

async def telegram_retry(func, *args, max_retries=3, **kwargs):
    """Функция retry для Telegram API calls"""
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except RetryAfter as e:
            if attempt == max_retries - 1:
                raise
            logger.info(f"Rate limited, waiting {e.retry_after}s (attempt {attempt + 1})")
            await asyncio.sleep(e.retry_after)
        except (TimedOut, NetworkError) as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # Exponential backoff
            logger.info(f"Network error, retrying in {wait_time}s (attempt {attempt + 1})")
            await asyncio.sleep(wait_time)
    
    raise Exception(f"Max retries ({max_retries}) exceeded")