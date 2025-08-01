"""
Тесты для основных хендлеров бота
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

# Мокаем рабочий бот для тестирования
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def mock_update():
    """Создаёт мок Update объекта"""
    update = MagicMock(spec=Update)
    update.effective_user = User(id=123, first_name="Test", is_bot=False)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.message.chat = Chat(id=123, type="private")
    update.message.text = "/start"
    return update

@pytest.fixture
def mock_context():
    """Создаёт мок Context объекта"""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context

class TestBotHandlers:
    """Тесты для хендлеров бота"""
    
    @pytest.mark.asyncio
    async def test_start_command_new_user(self, mock_update, mock_context):
        """Тест команды /start для нового пользователя"""
        # Импортируем функцию start из рабочего бота
        from working_bot import start
        
        # Выполняем команду
        await start(mock_update, mock_context)
        
        # Проверяем, что отправился приветственный текст
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Добро пожаловать" in call_args

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Тест rate limiting middleware"""
        from bot_middleware import RateLimiter
        
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Первые два запроса должны пройти
        assert limiter.is_allowed("user123") == True
        assert limiter.is_allowed("user123") == True
        
        # Третий запрос должен быть заблокирован
        assert limiter.is_allowed("user123") == False

    @pytest.mark.asyncio 
    async def test_health_check(self):
        """Тест health check системы"""
        from health_check import HealthChecker
        
        # Мокаем bot token для теста
        checker = HealthChecker("test_token")
        
        # Тест проверки переменных окружения
        env_check = checker.check_env_vars()
        assert "status" in env_check
        
        # Тест проверки базы данных
        db_check = checker.check_database()
        assert "status" in db_check

    def test_secure_logging(self):
        """Тест безопасного логирования"""
        from secure_logger import SecureFormatter
        import logging
        
        formatter = SecureFormatter()
        
        # Создаём тестовую запись с секретом
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="API key: sk-1234567890abcdef",
            args=(),
            exc_info=None
        )
        
        # Форматируем запись
        formatted = formatter.format(record)
        
        # Проверяем, что секрет скрыт
        assert "sk-1234567890abcdef" not in formatted
        assert "***HIDDEN***" in formatted

class TestDataValidation:
    """Тесты валидации данных"""
    
    def test_time_slot_validation(self):
        """Тест валидации временных слотов"""
        # Тест будет расширен при добавлении валидации
        pass
    
    def test_user_input_sanitization(self):
        """Тест санитизации пользовательского ввода"""
        # Тест для предотвращения XSS и injection атак
        pass

if __name__ == "__main__":
    pytest.main([__file__])