"""
Health check endpoints для мониторинга бота
"""
from datetime import datetime, timedelta
import json
import os
import logging
from telegram import Bot

logger = logging.getLogger(__name__)

class HealthChecker:
    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
        self.last_update_time = datetime.now()
        
    async def check_bot_api(self) -> dict:
        """Проверяет доступность Telegram Bot API"""
        try:
            me = await self.bot.get_me()
            return {
                "status": "healthy",
                "bot_username": me.username,
                "bot_id": me.id
            }
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": str(e)
            }
    
    def check_database(self) -> dict:
        """Проверяет доступность базы данных"""
        try:
            with open('data/database.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            masters_count = len(data.get('masters', []))
            return {
                "status": "healthy",
                "masters_count": masters_count,
                "file_exists": True
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_env_vars(self) -> dict:
        """Проверяет наличие необходимых переменных окружения"""
        required_vars = ['BOT_TOKEN', 'OPENAI_API_KEY']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            return {
                "status": "unhealthy",
                "missing_vars": missing_vars
            }
        
        return {
            "status": "healthy",
            "all_vars_present": True
        }
    
    def update_last_activity(self):
        """Обновляет время последней активности"""
        self.last_update_time = datetime.now()
    
    def check_recent_activity(self) -> dict:
        """Проверяет была ли недавняя активность"""
        time_since_update = datetime.now() - self.last_update_time
        
        if time_since_update > timedelta(minutes=10):
            return {
                "status": "warning",
                "last_activity": self.last_update_time.isoformat(),
                "minutes_since": int(time_since_update.total_seconds() / 60)
            }
        
        return {
            "status": "healthy",
            "last_activity": self.last_update_time.isoformat()
        }
    
    async def full_health_check(self) -> dict:
        """Полная проверка здоровья системы"""
        checks = {
            "telegram_api": await self.check_bot_api(),
            "database": self.check_database(),
            "environment": self.check_env_vars(),
            "activity": self.check_recent_activity(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Определяем общий статус
        all_healthy = all(
            check.get("status") == "healthy" 
            for check in checks.values() 
            if isinstance(check, dict) and "status" in check
        )
        
        checks["overall_status"] = "healthy" if all_healthy else "unhealthy"
        return checks

# Глобальный health checker
health_checker = None

def init_health_checker(bot_token: str):
    global health_checker
    health_checker = HealthChecker(bot_token)
    return health_checker