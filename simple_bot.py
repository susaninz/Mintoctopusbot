#!/usr/bin/env python3
"""
Упрощенная версия бота для тестирования основной логики
"""
import logging
import os
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для кнопок
MASTER_ROLE = "Я мну 🐙"
CLIENT_ROLE = "Хочу, чтобы меня помяли 🙏"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение с кнопками выбора роли."""
    reply_keyboard = [[MASTER_ROLE, CLIENT_ROLE]]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        f"Привет, {update.effective_user.mention_html()}! 🐙\n\n"
        "Я мудрый Осьминог, хранитель этого места.\n"
        "Чтобы начать, выбери, кто ты:",
        reply_markup=markup,
        parse_mode='HTML'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает все сообщения."""
    text = update.message.text
    user_id = update.effective_user.id
    
    logger.info(f"Получено сообщение от {user_id}: '{text}'")
    
    if text == MASTER_ROLE:
        await update.message.reply_text(
            "Великолепно! Ты выбрал стать мастером! 🌊\n\n"
            "Расскажи о себе: имя, опыт, услуги, свободное время и локации."
        )
    elif text == CLIENT_ROLE:
        await update.message.reply_text(
            "Чудесно! Добро пожаловать в заповедник исцеления! 🌿\n\n"
            "Здесь ты найдешь мастеров для восстановления сил."
        )
    else:
        await update.message.reply_text(
            f"Я получил твое сообщение: '{text}'\n"
            "Используй /start чтобы начать заново."
        )

def main() -> None:
    """Запускает бота."""
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        logger.error("Не найден TELEGRAM_TOKEN. Убедись, что он есть в .env файле.")
        return

    application = Application.builder().token(telegram_token).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🐙 Простой осьминог запущен и готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()