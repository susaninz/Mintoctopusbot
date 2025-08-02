"""
Telegram Notifier - отправляет уведомления о багах с интерактивными кнопками
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
import json
import os
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, admin_id: int = 78273571):
        # Используем тот же токен что и основной бот
        self.bot_token = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
        self.admin_id = admin_id
        self.bot = Bot(token=self.bot_token) if self.bot_token else None
        self.pending_notifications = []
        
        if not self.bot:
            logger.error("❌ BOT_TOKEN не найден для TelegramNotifier")
    
    async def send_critical_bug_notification(self, bug_analysis: Dict) -> bool:
        """Отправляет немедленное уведомление о критическом баге"""
        if not self.bot:
            logger.error("❌ Telegram бот не инициализирован")
            return False
            
        try:
            message = self._format_critical_bug_message(bug_analysis)
            keyboard = self._create_bug_action_keyboard(bug_analysis['bug_id'])
            
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            logger.info(f"✅ Критическое уведомление отправлено для бага {bug_analysis['bug_id']}")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Ошибка отправки критического уведомления: {e}")
            return False
    
    async def send_daily_bug_digest(self, bug_analyses: List[Dict]) -> bool:
        """Отправляет ежедневный дайджест обычных багов"""
        if not self.bot or not bug_analyses:
            return False
            
        try:
            message = self._format_digest_message(bug_analyses)
            keyboard = self._create_digest_keyboard(bug_analyses)
            
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            logger.info(f"✅ Дайджест отправлен: {len(bug_analyses)} багов")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Ошибка отправки дайджеста: {e}")
            return False
    
    async def send_auto_fix_notification(self, bug_id: str, fix_details: Dict) -> bool:
        """Уведомляет об автоматическом исправлении"""
        if not self.bot:
            return False
            
        try:
            message = self._format_auto_fix_message(bug_id, fix_details)
            
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode='HTML'
            )
            
            logger.info(f"✅ Уведомление об автофиксе отправлено для {bug_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Ошибка уведомления об автофиксе: {e}")
            return False
    
    def _format_critical_bug_message(self, bug_analysis: Dict) -> str:
        """Форматирует сообщение о критическом баге"""
        bug_id = bug_analysis.get('bug_id', 'Unknown')
        severity = bug_analysis.get('severity', 'normal').upper()
        bug_type = bug_analysis.get('bug_type', 'unknown')
        
        # Эмодзи в зависимости от серьезности
        severity_emoji = {
            'CRITICAL': '🔴',
            'HIGH': '🟡', 
            'NORMAL': '🟢'
        }.get(severity, '⚪')
        
        message = f"""
{severity_emoji} <b>БАГРЕПОРТ #{bug_id}</b> | {severity}

👤 <b>Пользователь:</b> {bug_analysis.get('reporter', 'Неизвестен')}
📝 <b>Проблема:</b> {bug_analysis.get('original_description', 'Описание отсутствует')}

🔍 <b>GPT АНАЛИЗ:</b>
{bug_analysis.get('analysis', 'Анализ недоступен')}

💻 <b>ПРОМПТ ДЛЯ CURSOR:</b>
<code>{bug_analysis.get('cursor_prompt', 'Промпт недоступен')}</code>

📊 <b>Детали:</b>
• Тип: {bug_type}
• Сложность: {bug_analysis.get('estimated_complexity', 'неизвестно')}
• Файлы: {', '.join(bug_analysis.get('affected_files', []))}

⏰ Анализ: {bug_analysis.get('analyzed_at', 'неизвестно')}
        """.strip()
        
        return message
    
    def _format_digest_message(self, bug_analyses: List[Dict]) -> str:
        """Форматирует дайджест багов"""
        total_bugs = len(bug_analyses)
        critical_count = len([b for b in bug_analyses if b.get('severity') == 'critical'])
        high_count = len([b for b in bug_analyses if b.get('severity') == 'high'])
        normal_count = total_bugs - critical_count - high_count
        
        message = f"""
📋 <b>ЕЖЕДНЕВНЫЙ ДАЙДЖЕСТ БАГОВ</b>

📊 <b>Всего: {total_bugs}</b>
🔴 Критических: {critical_count}
🟡 Высокий приоритет: {high_count} 
🟢 Обычных: {normal_count}

<b>СПИСОК БАГОВ:</b>
        """
        
        for i, bug in enumerate(bug_analyses[:5], 1):  # Показываем максимум 5
            severity_emoji = {
                'critical': '🔴',
                'high': '🟡',
                'normal': '🟢'
            }.get(bug.get('severity', 'normal'), '⚪')
            
            message += f"\n{i}. {severity_emoji} #{bug.get('bug_id', 'N/A')} - {bug.get('original_description', 'Без описания')[:50]}..."
        
        if total_bugs > 5:
            message += f"\n... и еще {total_bugs - 5} багов"
            
        message += f"\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        return message
    
    def _format_auto_fix_message(self, bug_id: str, fix_details: Dict) -> str:
        """Форматирует уведомление об автофиксе"""
        return f"""
🤖 <b>АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ</b>

📋 <b>Баг:</b> #{bug_id}
✅ <b>Статус:</b> {fix_details.get('status', 'Исправлен')}

🔧 <b>Что исправлено:</b>
{fix_details.get('description', 'Детали недоступны')}

📄 <b>Измененные файлы:</b>
{', '.join(fix_details.get('modified_files', []))}

🧪 <b>Тесты:</b> {fix_details.get('tests_passed', 'Не выполнялись')}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
        """.strip()
    
    def _create_bug_action_keyboard(self, bug_id: str) -> InlineKeyboardMarkup:
        """Создает клавиатуру для действий с багом"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Исправить", callback_data=f"bug_fix_{bug_id}"),
                InlineKeyboardButton("ℹ️ Нужно инфо", callback_data=f"bug_info_{bug_id}")
            ],
            [
                InlineKeyboardButton("⏰ Отложить", callback_data=f"bug_postpone_{bug_id}"),
                InlineKeyboardButton("📋 Подробнее", callback_data=f"bug_details_{bug_id}")
            ],
            [
                InlineKeyboardButton("❌ Отклонить", callback_data=f"bug_reject_{bug_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _create_digest_keyboard(self, bug_analyses: List[Dict]) -> InlineKeyboardMarkup:
        """Создает клавиатуру для дайджеста"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Исправить все", callback_data="bugs_fix_all"),
                InlineKeyboardButton("🔍 Детали", callback_data="bugs_show_details")
            ],
            [
                InlineKeyboardButton("🟡 Только приоритетные", callback_data="bugs_priority_only"),
                InlineKeyboardButton("⏰ Отложить все", callback_data="bugs_postpone_all")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def handle_bug_action_callback(self, callback_data: str, user_id: int) -> Dict:
        """Обрабатывает нажатия кнопок в уведомлениях о багах"""
        if user_id != self.admin_id:
            return {"success": False, "message": "Unauthorized"}
        
        try:
            action_parts = callback_data.split("_", 2)
            if len(action_parts) < 3:
                return {"success": False, "message": "Invalid callback format"}
            
            action_type = action_parts[1]  # fix, info, postpone, etc.
            bug_id = action_parts[2]
            
            response_message = ""
            
            if action_type == "fix":
                response_message = f"✅ Баг #{bug_id} отмечен для исправления"
                # Здесь можно добавить логику для автоматического исправления
                
            elif action_type == "info":
                response_message = f"ℹ️ Запрос дополнительной информации по багу #{bug_id}"
                # Логика для запроса дополнительной информации у пользователя
                
            elif action_type == "postpone":
                response_message = f"⏰ Баг #{bug_id} отложен"
                
            elif action_type == "details":
                response_message = f"📋 Подробная информация по багу #{bug_id}"
                # Можно отправить дополнительную информацию
                
            elif action_type == "reject":
                response_message = f"❌ Баг #{bug_id} отклонен"
            
            # Логируем действие
            logger.info(f"🎯 Админ действие: {action_type} для бага {bug_id}")
            
            return {
                "success": True,
                "action": action_type,
                "bug_id": bug_id,
                "message": response_message
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки callback: {e}")
            return {"success": False, "message": f"Error: {e}"}
    
    def add_to_pending(self, bug_analysis: Dict):
        """Добавляет баг в очередь для дайджеста"""
        if bug_analysis.get('severity') == 'critical':
            # Критические отправляем сразу
            asyncio.create_task(self.send_critical_bug_notification(bug_analysis))
        else:
            # Обычные добавляем в очередь
            self.pending_notifications.append(bug_analysis)
            logger.info(f"📋 Баг {bug_analysis.get('bug_id')} добавлен в очередь дайджеста")
    
    async def send_pending_digest(self):
        """Отправляет накопленные уведомления"""
        if self.pending_notifications:
            await self.send_daily_bug_digest(self.pending_notifications)
            self.pending_notifications.clear()
    
    def get_pending_count(self) -> int:
        """Возвращает количество багов в очереди"""
        return len(self.pending_notifications)

# Создаем глобальный экземпляр
telegram_notifier = TelegramNotifier()