"""
Обработчики команд администратора
"""
import logging
from typing import Dict, Any
from telegram import Update
from telegram.ext import ContextTypes

from bot.services.data_service import DataService
from bot.services.master_service import MasterService
from bot.utils.formatters import format_master_profile

logger = logging.getLogger(__name__)


class AdminHandlers:
    """Обработчики команд администратора."""
    
    def __init__(self, data_service: DataService):
        """
        Инициализация админ-обработчиков.
        
        Args:
            data_service: Сервис данных
        """
        self.data_service = data_service
        self.master_service = MasterService(data_service)
    
    def is_admin(self, user_id: str) -> bool:
        """
        Проверяет, является ли пользователь администратором.
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            bool: True если администратор
        """
        import os
        admin_ids = os.getenv("ADMIN_IDS", "").split(",")
        return str(user_id) in admin_ids
    
    async def show_pending_masters(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Показывает мастеров, ожидающих верификации.
        
        Args:
            update: Telegram update
            context: Telegram context
        """
        user_id = str(update.effective_user.id)
        
        if not self.is_admin(user_id):
            await update.message.reply_text("🚫 Только для администраторов")
            return
        
        pending_masters = self.master_service.get_pending_verification_masters()
        
        if not pending_masters:
            await update.message.reply_text("✅ Все мастера верифицированы!")
            return
        
        message = "🔍 **МАСТЕРА БЕЗ ВЕРИФИКАЦИИ:**\n\n"
        
        for i, master in enumerate(pending_masters, 1):
            name = master.get("name", "Без имени")
            handle = master.get("telegram_handle", "Без @username")
            slots_count = len(master.get("time_slots", []))
            bookings_count = len(master.get("bookings", []))
            
            message += (
                f"{i}. **{name}**\n"
                f"   📱 {handle}\n"
                f"   📅 Слотов: {slots_count} | Записей: {bookings_count}\n\n"
            )
        
        message += (
            "💡 **Как привязать мастера:**\n"
            "`/link_master Имя Мастера @telegram_id`\n\n"
            "📋 **Или попросите мастера:**\n"
            "1. Установить @username в Telegram\n"
            "2. Обновить таблицу с корректным @username\n"
            "3. Перезапустить бота"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def link_master_manually(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Ручная привязка мастера к telegram ID.
        
        Args:
            update: Telegram update
            context: Telegram context
        """
        user_id = str(update.effective_user.id)
        
        if not self.is_admin(user_id):
            await update.message.reply_text("🚫 Только для администраторов")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Неверный формат!\n\n"
                "Используйте: `/link_master Имя Мастера telegram_id`\n"
                "Пример: `/link_master Коля Богатищев 123456789`",
                parse_mode='Markdown'
            )
            return
        
        # Последний аргумент - telegram_id, остальные - имя
        telegram_id = context.args[-1]
        master_name = " ".join(context.args[:-1])
        
        if not telegram_id.isdigit():
            await update.message.reply_text("❌ Telegram ID должен быть числом!")
            return
        
        # Выполняем привязку
        success = self.master_service.manually_link_master(master_name, telegram_id)
        
        if success:
            await update.message.reply_text(
                f"✅ **Мастер привязан!**\n\n"
                f"👤 **{master_name}**\n"
                f"🆔 Telegram ID: `{telegram_id}`\n\n"
                f"Теперь мастер может войти в бота!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ **Ошибка привязки!**\n\n"
                f"Мастер '{master_name}' не найден в базе.\n"
                f"Проверьте правильность написания имени."
            )
    
    async def show_all_masters_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Показывает статус всех мастеров.
        
        Args:
            update: Telegram update
            context: Telegram context
        """
        user_id = str(update.effective_user.id)
        
        if not self.is_admin(user_id):
            await update.message.reply_text("🚫 Только для администраторов")
            return
        
        all_masters = self.data_service.get_all_masters()
        
        if not all_masters:
            await update.message.reply_text("😞 Мастеров нет в базе")
            return
        
        verified_count = 0
        pending_count = 0
        
        message = "📊 **СТАТУС ВСЕХ МАСТЕРОВ:**\n\n"
        
        for master in all_masters:
            name = master.get("name", "Без имени")
            telegram_id = master.get("telegram_id", "")
            handle = master.get("telegram_handle", "Нет @username")
            slots_count = len(master.get("time_slots", []))
            bookings_count = len(master.get("bookings", []))
            
            if telegram_id.isdigit() and len(telegram_id) >= 8:
                status = "✅ Верифицирован"
                verified_count += 1
            else:
                status = "❌ Ожидает верификации"
                pending_count += 1
            
            message += (
                f"👤 **{name}**\n"
                f"   🔹 {status}\n"
                f"   📱 {handle}\n"
                f"   📅 {slots_count} слотов, {bookings_count} записей\n\n"
            )
        
        summary = (
            f"📈 **ИТОГО:**\n"
            f"✅ Верифицировано: {verified_count}\n"
            f"❌ Ожидают: {pending_count}\n"
            f"👥 Всего: {len(all_masters)}"
        )
        
        await update.message.reply_text(message + summary, parse_mode='Markdown')
    
    async def help_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Показывает справку по админ-командам.
        
        Args:
            update: Telegram update
            context: Telegram context
        """
        user_id = str(update.effective_user.id)
        
        if not self.is_admin(user_id):
            await update.message.reply_text("🚫 Только для администраторов")
            return
        
        help_text = """
🔧 **КОМАНДЫ АДМИНИСТРАТОРА:**

📋 `/pending_masters` - Показать неверифицированных мастеров
🔗 `/link_master Имя telegram_id` - Ручная привязка мастера
📊 `/masters_status` - Статус всех мастеров
❓ `/admin_help` - Эта справка

💡 **Примеры:**
• `/link_master Коля Богатищев 123456789`
• `/link_master Аня Каширина 987654321`

⚠️ **Важно:**
- Telegram ID можно узнать, написав @userinfobot
- Имя должно точно совпадать с данными в базе
- После привязки мастер сразу получает доступ
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')