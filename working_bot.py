#!/usr/bin/env python3
"""
Рабочая версия бота с полным функционалом (без GPT для упрощения)
"""
import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.gpt_service import GPTService
from bot.services.data_service import DataService
from bot.handlers.admin_handlers import AdminHandlers
from services.bug_reporter import bug_reporter
from services.safe_data_manager import safe_data_manager
import utils
from utils import format_date_for_user, format_slot_for_user, format_slots_list
from bot_middleware import with_error_handling, with_rate_limiting, telegram_retry
from secure_logger import setup_secure_logging, secure_log_user_action
from health_check import init_health_checker
# from health_server import start_health_server, set_telegram_application  # Импортируем только в production

# Загружаем переменные окружения
load_dotenv()

# Настройка безопасного логирования
setup_secure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Константы для кнопок
# Импортируем все константы из bot.constants
from bot.constants import (
    MASTER_ROLE, CLIENT_ROLE, MY_SLOTS, ADD_SLOTS, MY_PROFILE, EDIT_PROFILE,
    VIEW_MASTERS, VIEW_DEVICES, VIEW_FREE_SLOTS, MY_BOOKINGS, 
    BACK_TO_MENU, CHANGE_ROLE, REPORT_BUG, MY_VIBRO_CHAIR
)

# Хранилище состояний пользователей
user_states = {}

# Инициализация планировщика для напоминаний
scheduler = AsyncIOScheduler()
application_instance = None  # Будет установлен в main()
health_checker = None  # Будет установлен в main()

# Инициализация сервисов
gpt_service = GPTService()
data_service = DataService()
admin_handlers = AdminHandlers(data_service)

def get_user_state(user_id: str):
    """Получает состояние пользователя или создает новое."""
    if user_id not in user_states:
        user_states[user_id] = {"role": None, "awaiting": None}
    return user_states[user_id]

def load_data():
    """Загружает данные из JSON файла через безопасный менеджер."""
    return safe_data_manager.get_data()

def save_data(data, reason="update"):
    """Сохраняет данные через безопасный менеджер."""
    safe_data_manager.data = data
    return safe_data_manager.save_data(reason)

def get_main_keyboard():
    """Клавиатура выбора роли."""
    return ReplyKeyboardMarkup([[MASTER_ROLE, CLIENT_ROLE]], resize_keyboard=True, one_time_keyboard=True)

def get_master_keyboard():
    """Клавиатура для мастера."""
    return ReplyKeyboardMarkup([
        [MY_SLOTS, ADD_SLOTS],
        [MY_PROFILE, EDIT_PROFILE],
        [VIEW_MASTERS, VIEW_FREE_SLOTS],
        [CHANGE_ROLE, REPORT_BUG]
    ], resize_keyboard=True)

def get_client_keyboard():
    """Клавиатура для гостя."""
    return ReplyKeyboardMarkup([
        [VIEW_MASTERS, VIEW_DEVICES],
        [VIEW_FREE_SLOTS, MY_BOOKINGS],
        [CHANGE_ROLE, REPORT_BUG]
    ], resize_keyboard=True)

def get_device_owner_keyboard():
    """Клавиатура для владельца девайса (Фила)."""
    return ReplyKeyboardMarkup([
        [MY_VIBRO_CHAIR, VIEW_DEVICES],
        [VIEW_MASTERS, VIEW_FREE_SLOTS],
        [MY_BOOKINGS, CHANGE_ROLE],
        [REPORT_BUG]
    ], resize_keyboard=True)

def generate_reminder_text(is_master: bool, master_name: str, client_name: str, slot_time: str, slot_location: str) -> str:
    """Генерирует текст напоминания в стиле заповедного осьминога."""
    if is_master:
        return (
            f"🌊 Мудрые течения напоминают, {master_name}!\n\n"
            f"Через 15 минут к тебе приплывет {client_name} за исцелением.\n"
            f"🕐 Время: {slot_time}\n"
            f"📍 Место: {slot_location}\n\n"
            f"Да направят тебя древние силы глубин! 🐙✨"
        )
    else:
        return (
            f"🌊 Глубины шепчут тебе, {client_name}!\n\n"
            f"Через 15 минут начнется твой сеанс с мастером {master_name}.\n"
            f"🕐 Время: {slot_time}\n" 
            f"📍 Место: {slot_location}\n\n"
            f"Приготовься принять дары исцеления от заповедного целителя! 🐙💫"
        )

async def send_reminder(user_id: str, reminder_text: str):
    """Отправляет напоминание пользователю."""
    try:
        if application_instance:
            await application_instance.bot.send_message(chat_id=user_id, text=reminder_text)
            logger.info(f"Напоминание отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания пользователю {user_id}: {e}")

def schedule_single_reminder(booking_data: dict, reminder_time: datetime, reminder_type: str, is_equipment: bool = False):
    """Планирует одно напоминание с персональным GPT-сообщением."""
    try:
        booking_id = booking_data.get('id', 'unknown')
        
        # Генерируем персональные напоминания через GPT
        if is_equipment:
            # Для оборудования только напоминание клиенту
            client_reminder = gpt_service.generate_personalized_reminder(
                is_master=False,
                master_name=booking_data['master_name'],
                client_name=booking_data['client_name'],
                slot_time=f"{booking_data['slot_start_time']}-{booking_data['slot_end_time']}",
                slot_location=booking_data.get('slot_location', 'Заповедник'),
                reminder_type=reminder_type
            )
            
            scheduler.add_job(
                send_reminder,
                'date', 
                run_date=reminder_time,
                args=[booking_data['client_id'], client_reminder],
                id=f"reminder_client_{booking_id}_{reminder_type}"
            )
        else:
            # Для мастеров - напоминания обеим сторонам
            master_reminder = gpt_service.generate_personalized_reminder(
                is_master=True,
                master_name=booking_data['master_name'],
                client_name=booking_data['client_name'],
                slot_time=f"{booking_data['slot_start_time']}-{booking_data['slot_end_time']}",
                slot_location=booking_data.get('slot_location', 'Заповедник'),
                reminder_type=reminder_type
            )
            
            client_reminder = gpt_service.generate_personalized_reminder(
                is_master=False,
                master_name=booking_data['master_name'],
                client_name=booking_data['client_name'],
                slot_time=f"{booking_data['slot_start_time']}-{booking_data['slot_end_time']}",
                slot_location=booking_data.get('slot_location', 'Заповедник'),
                reminder_type=reminder_type
            )
            
            scheduler.add_job(
                send_reminder,
                'date',
                run_date=reminder_time,
                args=[booking_data['master_id'], master_reminder],
                id=f"reminder_master_{booking_id}_{reminder_type}"
            )
            
            scheduler.add_job(
                send_reminder,
                'date', 
                run_date=reminder_time,
                args=[booking_data['client_id'], client_reminder],
                id=f"reminder_client_{booking_id}_{reminder_type}"
            )
        
        logger.info(f"Напоминание {reminder_type} запланировано на {reminder_time} для {booking_id}")
        
    except Exception as e:
        logger.error(f"Ошибка планирования напоминания {reminder_type}: {e}")

def schedule_reminder(booking_data: dict, is_equipment: bool = False):
    """Планирует напоминания за 1 час и 15 минут до сеанса."""
    try:
        # Парсим время сеанса
        slot_datetime_str = f"{booking_data['slot_date']} {booking_data['slot_start_time']}"
        slot_datetime = datetime.strptime(slot_datetime_str, "%Y-%m-%d %H:%M")
        
        # Вычисляем время напоминаний
        reminder_1hour = slot_datetime - timedelta(hours=1)
        reminder_15min = slot_datetime - timedelta(minutes=15)
        
        current_time = datetime.now()
        
        # Планируем напоминание за 1 час (если ещё не прошло)
        if reminder_1hour > current_time:
            schedule_single_reminder(booking_data, reminder_1hour, "1_hour", is_equipment)
        
        # Планируем напоминание за 15 минут (если ещё не прошло)
        if reminder_15min > current_time:
            schedule_single_reminder(booking_data, reminder_15min, "15_min", is_equipment)
        
        logger.info(f"Напоминания запланированы для бронирования {booking_data.get('id', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Ошибка планирования напоминания: {e}")

async def test_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Создает тестовое напоминание через 1 минуту для демонстрации."""
    user_id = str(update.effective_user.id)
    
    # Создаем тестовые данные
    test_booking = {
        'booking_id': f'test_{user_id}_{datetime.now().timestamp()}',
        'master_id': user_id,
        'client_id': user_id,
        'master_name': 'Мастер Ваня',
        'client_name': update.effective_user.first_name or 'Гость',
        'date': datetime.now().strftime('%Y-%m-%d'),
        'start_time': (datetime.now() + timedelta(minutes=1, seconds=15)).strftime('%H:%M'),
        'end_time': (datetime.now() + timedelta(minutes=2, seconds=15)).strftime('%H:%M'),
        'location': 'Тестовая локация'
    }
    
    # Планируем напоминание через 1 минуту
    reminder_time = datetime.now() + timedelta(minutes=1)
    
    reminder_text = generate_reminder_text(
        is_master=True,
        master_name=test_booking['master_name'],
        client_name=test_booking['client_name'],
        slot_time=f"{test_booking['start_time']}-{test_booking['end_time']}",
        slot_location=test_booking['location']
    )
    
    scheduler.add_job(
        send_reminder,
        'date',
        run_date=reminder_time,
        args=[user_id, reminder_text],
        id=f"test_reminder_{user_id}"
    )
    
    await update.message.reply_text(
        f"🧪 Тестовое напоминание запланировано!\n\n"
        f"Получишь его через 1 минуту в {reminder_time.strftime('%H:%M:%S')} 🐙"
    )

async def show_slots_with_management(update: Update, context: ContextTypes.DEFAULT_TYPE, master: dict):
    """Показывает слоты мастера с кнопками управления."""
    from datetime import datetime
    
    all_slots = master.get("time_slots", [])
    
    # Фильтруем только будущие слоты
    now = datetime.now()
    slots = []
    for slot in all_slots:
        slot_date = slot.get("date")
        slot_start_time = slot.get("start_time")
        
        if not slot_date or not slot_start_time:
            continue
            
        try:
            slot_datetime = datetime.strptime(f"{slot_date} {slot_start_time}", "%Y-%m-%d %H:%M")
            if slot_datetime > now:
                slots.append(slot)
        except ValueError:
            continue
    
    if not slots:
        await update.message.reply_text(
            "📭 У тебя нет активных слотов.\n\n"
            "Все прошедшие слоты автоматически скрыты. "
            "Используй 'Добавить слоты ➕' чтобы создать новые!"
        )
        return
    
    for i, slot in enumerate(slots):
        slot_text = (
            f"📅 **Слот {i+1}:**\n"
            f"🗓 {format_slot_for_user(slot)}\n"
        )
        
        # Создаем inline кнопки для каждого слота
        keyboard = []
        
        # Проверяем есть ли запись на этот слот
        bookings = master.get("bookings", [])
        slot_booking = None
        for booking in bookings:
            if (booking.get("slot_date") == slot['date'] and 
                booking.get("slot_start_time") == slot['start_time'] and
                booking.get("status") == "confirmed"):
                slot_booking = booking
                break
        
        if slot_booking:
            slot_text += f"👤 **Забронирован:** {slot_booking.get('client_name', 'Неизвестный')}\n"
            keyboard.append([
                InlineKeyboardButton("❌ Отменить запись", callback_data=f"cancel_booking_{i}"),
                InlineKeyboardButton("✏️ Изменить время", callback_data=f"edit_slot_{i}")
            ])
        else:
            slot_text += "🟢 **Свободен**\n"
            keyboard.append([
                InlineKeyboardButton("❌ Удалить слот", callback_data=f"delete_slot_{i}"),
                InlineKeyboardButton("✏️ Изменить время", callback_data=f"edit_slot_{i}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(slot_text, parse_mode='Markdown', reply_markup=reply_markup)

async def edit_profile_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает новое описание профиля мастера."""
    user_id = str(update.effective_user.id)
    user_state = get_user_state(user_id)
    user_state["awaiting"] = "new_profile"
    
    await update.message.reply_text(
        "🌊 Расскажи о себе заново, и мудрый Осьминог обновит твой профиль!\n\n"
        "Укажи:\n"
        "• Имя\n"
        "• Опыт и подход\n"
        "• Услуги которые предлагаешь\n\n"
        "Я сгенерирую новое фэнтези-описание в стиле заповедника! 🐙✨",
        reply_markup=ReplyKeyboardRemove()
    )

async def process_add_slots(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает добавление новых слотов через GPT парсинг."""
    user_id = str(update.effective_user.id)
    slots_text = update.message.text
    
    await update.message.reply_text("🤔 Осьминог размышляет над твоими словами...")
    
    try:
        # Используем GPT для парсинга слотов
        new_slots = gpt_service.parse_time_slots(slots_text)
        
        if not new_slots:
            await update.message.reply_text(
                "😔 Осьминог не смог понять, что ты имеешь в виду. \n\n"
                "Попробуй написать по-другому, например:\n"
                "• 'Завтра с 14:00 до 16:00 в бане'\n"
                "• 'В субботу в 18:00 на час в глэмпинге'",
                reply_markup=get_master_keyboard()
            )
            user_states[user_id] = {"role": "master", "awaiting": None}
            return
        
        # Загружаем данные и находим мастера
        data = load_data()
        master = None
        for m in data.get("masters", []):
            if m.get("telegram_id") == user_id:
                master = m
                break
        
        if not master:
            await update.message.reply_text(
                "Ошибка: профиль мастера не найден.", 
                reply_markup=get_master_keyboard()
            )
            user_states[user_id] = {"role": "master", "awaiting": None}
            return
        
        # Добавляем новые слоты
        if "time_slots" not in master:
            master["time_slots"] = []
        
        master["time_slots"].extend(new_slots)
        
        # Сохраняем данные
        save_data(data)
        
        # Формируем ответ с красивым отображением
        formatted_slots = []
        for slot in new_slots:
            formatted_slots.append(format_slot_for_user(slot))
        
        slots_list = "\n".join([f"• {slot}" for slot in formatted_slots])
        
        await update.message.reply_text(
            f"✅ Отлично! Осьминог добавил {len(new_slots)} новых слотов:\n\n"
            f"{slots_list}\n\n"
            f"Теперь гости смогут записаться к тебе! 🐙✨",
            reply_markup=get_master_keyboard()
        )
        
    except Exception as e:
        # Детальное логирование для диагностики
        logger.error(f"ДЕТАЛЬНАЯ ОШИБКА при добавлении слотов: {e}")
        logger.error(f"Тип ошибки: {type(e).__name__}")
        logger.error(f"Текст слотов: {slots_text}")
        
        import traceback
        logger.error(f"Полный traceback: {traceback.format_exc()}")
        
        await update.message.reply_text(
            f"😱 Ошибка при добавлении слотов:\n{str(e)[:200]}\n\nПопробуй еще раз или обратись к администратору!",
            reply_markup=get_master_keyboard()
        )
    
    # Сбрасываем состояние
    user_states[user_id] = {"role": "master", "awaiting": None}

async def process_decline_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает причину отклонения записи."""
    user_id = str(update.effective_user.id)
    user_state = get_user_state(user_id)
    reason = update.message.text
    
    # Извлекаем индекс бронирования
    awaiting = user_state.get("awaiting", "")
    booking_index = int(awaiting.split("_")[2])
    
    data = load_data()
    master = None
    for m in data.get("masters", []):
        if m.get("telegram_id") == user_id:
            master = m
            break
    
    if not master:
        await update.message.reply_text("Ошибка: мастер не найден.", reply_markup=get_master_keyboard())
        user_states[user_id] = {"role": "master", "awaiting": None}
        return
    
    bookings = master.get("bookings", [])
    if booking_index >= len(bookings):
        await update.message.reply_text("Ошибка: запись не найдена.", reply_markup=get_master_keyboard())
        user_states[user_id] = {"role": "master", "awaiting": None}
        return
    
    booking = bookings[booking_index]
    client_id = booking.get("client_id")
    client_name = booking.get("client_name", "Гость")
    
    # Отклоняем запись
    booking["status"] = "declined"
    booking["decline_reason"] = reason
    save_data(data)
    
    slot_text = f"{format_date_for_user(booking.get('slot_date', ''))} с {booking.get('slot_start_time')} до {booking.get('slot_end_time')}"
    
    await update.message.reply_text(
        f"❌ Запись отклонена.\n\n"
        f"👤 Гость: {client_name}\n"
        f"📅 Время: {slot_text}\n"
        f"💬 Причина: {reason}\n\n"
        f"Осьминог передал сообщение гостю.",
        reply_markup=get_master_keyboard()
    )
    
    # Уведомляем клиента
    try:
        decline_message = (
            f"❌ **Запись отклонена**\n\n"
            f"🐙 Мастер: {master.get('name')}\n"
            f"📅 Время: {slot_text}\n"
            f"💬 Причина: {reason}\n\n"
            f"Не расстраивайся! В заповеднике много других мастеров ждут тебя 🌊"
        )
        
        await application_instance.bot.send_message(
            chat_id=client_id,
            text=decline_message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об отклонении клиенту {client_id}: {e}")
    
    # Сбрасываем состояние
    user_states[user_id] = {"role": "master", "awaiting": None}

async def process_new_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает новое описание профиля мастера."""
    user_id = str(update.effective_user.id)
    new_profile_text = update.message.text
    
    # Создаем улучшенное фэнтези-описание с GPT
    master_name = update.effective_user.first_name or "Мастер"
    
    try:
        extracted_data, new_fantasy_description = gpt_service.process_master_profile(new_profile_text)
        
        # Обновляем имя, если GPT извлек его из профиля
        if extracted_data.get("name"):
            master_name = extracted_data["name"]
    except Exception as e:
        logger.error(f"Ошибка GPT обработки: {e}")
        # Fallback на базовое описание
        new_fantasy_description = f"Осьминог видит обновленную силу в {master_name}. Его новые слова звучат как песни древних глубин, обещая еще более глубокое исцеление."
        extracted_data = {
            "name": master_name,
            "services": ["массаж", "целительство"],
            "time_slots": [],
            "locations": ["Баня"]
        }
    
    data = load_data()
    
    # Находим и обновляем мастера
    for master in data.get("masters", []):
        if master.get("telegram_id") == user_id:
            master["original_description"] = new_profile_text
            master["fantasy_description"] = new_fantasy_description
            master["name"] = master_name
            # Обновляем услуги и слоты если GPT их извлек
            if extracted_data.get("services"):
                master["services"] = extracted_data["services"]
            if extracted_data.get("time_slots"):
                # Добавляем новые слоты к существующим
                existing_slots = master.get("time_slots", [])
                for new_slot in extracted_data["time_slots"]:
                    # Проверяем, нет ли уже такого слота
                    if not any(s["date"] == new_slot["date"] and s["start_time"] == new_slot["start_time"] 
                              for s in existing_slots):
                        existing_slots.append(new_slot)
                master["time_slots"] = existing_slots
            break
    
    save_data(data)
    
    await update.message.reply_text(
        f"✨ Профиль обновлен, {master_name}!\n\n"
        f"🎭 **Новое фэнтези-описание:**\n_{new_fantasy_description}_\n\n"
        "Твоя сущность в заповеднике обновлена! 🐙",
        parse_mode='Markdown',
        reply_markup=get_master_keyboard()
    )
    
    # Сбрасываем состояние
    user_state = get_user_state(user_id)
    user_state["awaiting"] = None

@with_rate_limiting
@with_error_handling
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все inline кнопки."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Логируем callback действие
    secure_log_user_action(logger, update.effective_user.id, "callback_query", callback_data=callback_data)
    
    # Обработка кнопок для клиентов
    if callback_data.startswith("select_master_"):
        master_id = callback_data.split("_", 2)[2]
        await show_master_details(update, context, master_id)
        return
    
    elif callback_data.startswith("book_slot_"):
        parts = callback_data.split("_")
        master_id = parts[2]
        slot_index = parts[3]
        await process_booking_request(update, context, master_id, slot_index)
        return
    
    elif callback_data == "back_to_masters":
        await show_masters_list(update, context)
        return
    
    elif callback_data == "back_to_client_menu":
        user_id = str(query.from_user.id)
        user_states[user_id] = {"role": "client", "awaiting": None}
        await query.edit_message_text("🌊 Главное меню гостя:", reply_markup=get_client_keyboard())
        return
    
    # Обработка просмотра слотов по времени
    elif callback_data.startswith("slots_date_"):
        selected_date = callback_data.split("_", 2)[2]
        await show_slots_by_date(update, context, selected_date)
        return
    
    elif callback_data == "slots_custom_date":
        await query.edit_message_text(
            "📅 **Выбор даты**\n\n"
            "Введи дату в формате ДД.ММ.ГГГГ\n"
            "Например: 15.01.2025\n\n"
            "Или используй кнопки выше для быстрого выбора.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад к датам", callback_data="slots_menu")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    elif callback_data == "slots_menu":
        await show_free_slots_menu(update, context)
        return
    
    elif callback_data.startswith("book_time_"):
        parts = callback_data.split("_")
        master_id = parts[2]
        slot_time = parts[3]
        slot_date = parts[4]
        await process_time_booking_request(update, context, master_id, slot_time, slot_date)
        return
    
    elif callback_data == "my_bookings":
        await show_client_bookings(update, context)
        return
    
    # Обработка девайсов
    elif callback_data.startswith("device_info_"):
        device_id = callback_data.split("_", 2)[2]
        await show_device_details(update, context, device_id)
        return
    
    elif callback_data == "devices_list":
        await show_devices_list(update, context)
        return
    
    elif callback_data.startswith("book_device_"):
        device_id = callback_data.split("_", 2)[2]
        await show_device_booking_slots(update, context, device_id)
        return
    
    elif callback_data.startswith("device_slots_"):
        # Правильно парсим device_slots_vibro_chair_2025-08-02
        # Используем split с ограничением, чтобы корректно извлечь device_id и дату
        prefix = "device_slots_"
        remainder = callback_data[len(prefix):]
        # Дата всегда в конце в формате YYYY-MM-DD, найдем её
        parts = remainder.rsplit("_", 1)  # Разделяем справа на 2 части
        device_id = parts[0]  # vibro_chair
        date_str = parts[1]   # 2025-08-02
        await show_device_day_slots(update, context, device_id, date_str)
        return
    
    elif callback_data.startswith("confirm_device_booking_"):
        # Правильно парсим confirm_device_booking_vibro_chair_2025-08-02_09:00
        prefix = "confirm_device_booking_"
        remainder = callback_data[len(prefix):]
        # Время всегда в конце в формате HH:MM, найдем его
        parts = remainder.rsplit("_", 1)  # Разделяем справа на 2 части: "vibro_chair_2025-08-02" и "09:00"
        start_time = parts[1]  # 09:00
        date_and_device = parts[0]  # vibro_chair_2025-08-02
        # Теперь разделяем дату и device_id
        date_parts = date_and_device.rsplit("_", 1)  # Разделяем справа: "vibro_chair" и "2025-08-02"
        device_id = date_parts[0]  # vibro_chair
        date_str = date_parts[1]   # 2025-08-02
        await process_device_booking(update, context, device_id, date_str, start_time)
        return
    
    # Обработка подтверждения/отклонения записей мастерами
    elif callback_data.startswith("confirm_booking_") or callback_data.startswith("decline_booking_"):
        await handle_booking_response(update, context, callback_data)
        return
    
    # Обработка кнопок управления слотами мастеров
    user_id = str(query.from_user.id)
    data = load_data()
    
    # Находим мастера
    master = None
    for m in data.get("masters", []):
        if m.get("telegram_id") == user_id:
            master = m
            break
    
    if not master:
        await query.edit_message_text("❌ Ошибка: профиль мастера не найден.")
        return
    
    if callback_data.startswith("delete_slot_"):
        slot_index = int(callback_data.split("_")[-1])
        await delete_slot(query, master, slot_index, data)
    
    elif callback_data.startswith("cancel_booking_"):
        slot_index = int(callback_data.split("_")[-1])
        await cancel_booking(query, master, slot_index, data)
    
    elif callback_data.startswith("edit_slot_"):
        slot_index = int(callback_data.split("_")[-1])
        await edit_slot_request(query, master, slot_index)
    
    # Обработка багрепортов
    elif callback_data.startswith("bug_"):
        if callback_data == "bug_cancel":
            await query.edit_message_text("❌ Отменено. Если возникнут проблемы, используй /bug")
        elif callback_data in ["bug_critical", "bug_normal", "bug_suggestion", "bug_problem"]:
            bug_type = callback_data.split("_")[1] if callback_data != "bug_problem" else "problem"
            await bug_reporter.handle_bug_type_selection(update, context, bug_type)
        elif callback_data == "bug_my_reports":
            # Временная заглушка - показываем что функция не готова
            await query.edit_message_text(
                "📋 **Мои отчеты**\n\n"
                "⚠️ Функция в разработке\n\n"
                "Пока все отчеты отправляются напрямую админу для быстрого реагирования.\n"
                "Система истории отчетов будет добавлена в следующих версиях.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад", callback_data="bug_cancel")]
                ]),
                parse_mode='Markdown'
            )
    
    # Обработка отмены записей на виброкресло
    elif callback_data.startswith("cancel_vibro_"):
        booking_id = callback_data.replace("cancel_vibro_", "")
        await handle_vibro_booking_cancel(update, context, booking_id)
        return
    
    # Обработка возврата в меню владельца девайса
    elif callback_data == "back_to_device_menu":
        user_id = str(query.from_user.id)
        user_state = user_states.get(user_id, {})
        
        if user_state.get("is_device_owner"):
            await query.edit_message_text(
                "🪑 **Меню владельца виброкресла**\n\n"
                "Выбери действие:",
                reply_markup=get_device_owner_keyboard()
            )
        else:
            await query.edit_message_text(
                "🌊 Главное меню гостя:",
                reply_markup=get_client_keyboard()
            )
        return

async def handle_booking_response(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str) -> None:
    """Обрабатывает подтверждение или отклонение записи мастером."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    # Определяем действие и индекс бронирования
    if callback_data.startswith("confirm_booking_"):
        action = "confirm"
        booking_index = int(callback_data.split("_")[2])
    elif callback_data.startswith("decline_booking_"):
        action = "decline"
        booking_index = int(callback_data.split("_")[2])
    else:
        await query.edit_message_text("Неизвестная команда.")
        return
    
    data = load_data()
    master = None
    for m in data.get("masters", []):
        if m.get("telegram_id") == user_id:
            master = m
            break
    
    if not master:
        await query.edit_message_text("Мастер не найден.")
        return
    
    bookings = master.get("bookings", [])
    if booking_index >= len(bookings):
        await query.edit_message_text("Запись не найдена.")
        return
    
    booking = bookings[booking_index]
    client_id = booking.get("client_id")
    client_name = booking.get("client_name", "Гость")
    slot_text = f"{format_date_for_user(booking.get('slot_date', ''))} с {booking.get('slot_start_time')} до {booking.get('slot_end_time')}"
    
    if action == "confirm":
        # Подтверждаем запись
        booking["status"] = "confirmed"
        save_data(data)
        
        await query.edit_message_text(
            f"✅ Запись подтверждена!\n\n"
            f"👤 Гость: {client_name}\n"
            f"📅 Время: {slot_text}\n\n"
            f"Осьминог передал подтверждение гостю! 🐙"
        )
        
        # Уведомляем клиента
        try:
            confirmation_message = (
                f"✅ **Запись подтверждена!**\n\n"
                f"🐙 Мастер: {master.get('name')}\n"
                f"📅 Время: {slot_text}\n"
                f"📍 Место: {booking.get('location', 'Заповедник')}\n\n"
                f"Осьминог ждёт тебя! Приходи вовремя 🌊✨"
            )
            
            await application_instance.bot.send_message(
                chat_id=client_id,
                text=confirmation_message,
                parse_mode='Markdown'
            )
            
            # Устанавливаем напоминание за 15 минут до сеанса
            slot_datetime = datetime.fromisoformat(f"{booking.get('slot_date')} {booking.get('slot_start_time')}:00")
            reminder_time = slot_datetime - timedelta(minutes=15)
            
            if reminder_time > datetime.now():
                scheduler.add_job(
                    send_reminder,
                    'date',
                    run_date=reminder_time,
                    args=[client_id, f"⏰ Напоминание: через 15 минут у тебя сеанс с {master.get('name')}!"],
                    id=f"reminder_client_{client_id}_{booking_index}"
                )
                
                # Напоминание мастеру
                scheduler.add_job(
                    send_reminder,
                    'date',
                    run_date=reminder_time,
                    args=[user_id, f"⏰ Напоминание: через 15 минут у тебя сеанс с {client_name}!"],
                    id=f"reminder_master_{user_id}_{booking_index}"
                )
            
        except Exception as e:
            logger.error(f"Ошибка отправки подтверждения клиенту {client_id}: {e}")
    
    elif action == "decline":
        # Запрашиваем причину отклонения
        user_states[user_id] = {"role": "master", "awaiting": f"decline_reason_{booking_index}"}
        
        await query.edit_message_text(
            f"❌ Укажи причину отклонения записи для гостя {client_name}:\n"
            f"📅 {slot_text}\n\n"
            f"Напиши причину (она будет передана гостю):"
        )

async def delete_slot(query, master: dict, slot_index: int, data: dict):
    """Удаляет слот, уведомляя клиентов если есть бронирование."""
    slots = master.get("time_slots", [])
    
    if slot_index >= len(slots):
        await query.edit_message_text("❌ Слот не найден.")
        return
    
    slot = slots[slot_index]
    
    # Проверяем есть ли бронирование
    bookings = master.get("bookings", [])
    slot_booking = None
    for booking in bookings:
        if (booking.get("slot_date") == slot['date'] and 
            booking.get("slot_start_time") == slot['start_time'] and
            booking.get("status") == "confirmed"):
            slot_booking = booking
            break
    
    if slot_booking:
        # Уведомляем клиента об отмене
        client_id = slot_booking.get("client_id")
        if client_id:
            cancel_message = generate_cancellation_message(
                master["name"], 
                slot_booking.get("client_name", "Гость"),
                f"{slot['date']} с {slot['start_time']} до {slot['end_time']}",
                slot.get('location', 'заповедник'),
                "Мастер удалил этот слот"
            )
            
            try:
                if application_instance:
                    await application_instance.bot.send_message(chat_id=client_id, text=cancel_message)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления клиенту {client_id}: {e}")
        
        # Удаляем бронирование
        master["bookings"] = [b for b in bookings if b != slot_booking]
    
    # Удаляем слот
    master["time_slots"].pop(slot_index)
    save_data(data)
    
    await query.edit_message_text(
        f"✅ Слот удален: {slot['date']} с {slot['start_time']} до {slot['end_time']}\n"
        + ("Клиент уведомлен об отмене." if slot_booking else "")
    )

async def cancel_booking(query, master: dict, slot_index: int, data: dict):
    """Отменяет бронирование слота."""
    slots = master.get("time_slots", [])
    
    if slot_index >= len(slots):
        await query.edit_message_text("❌ Слот не найден.")
        return
    
    slot = slots[slot_index]
    
    # Находим и удаляем бронирование
    bookings = master.get("bookings", [])
    slot_booking = None
    for booking in bookings:
        if (booking.get("slot_date") == slot['date'] and 
            booking.get("slot_start_time") == slot['start_time'] and
            booking.get("status") == "confirmed"):
            slot_booking = booking
            break
    
    if slot_booking:
        client_id = slot_booking.get("client_id")
        if client_id:
            cancel_message = generate_cancellation_message(
                master["name"], 
                slot_booking.get("client_name", "Гость"),
                f"{slot['date']} с {slot['start_time']} до {slot['end_time']}",
                slot.get('location', 'заповедник'),
                "Мастер отменил запись"
            )
            
            try:
                if application_instance:
                    await application_instance.bot.send_message(chat_id=client_id, text=cancel_message)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления клиенту {client_id}: {e}")
        
        # Удаляем бронирование
        master["bookings"] = [b for b in bookings if b != slot_booking]
        save_data(data)
        
        await query.edit_message_text(
            f"✅ Запись отменена: {slot['date']} с {slot['start_time']} до {slot['end_time']}\n"
            "Клиент уведомлен об отмене."
        )
    else:
        await query.edit_message_text("❌ Бронирование не найдено.")

async def edit_slot_request(query, master: dict, slot_index: int):
    """Запрашивает изменение времени слота."""
    slots = master.get("time_slots", [])
    
    if slot_index >= len(slots):
        await query.edit_message_text("❌ Слот не найден.")
        return
    
    slot = slots[slot_index]
    await query.edit_message_text(
        f"✏️ Изменение слота: {slot['date']} с {slot['start_time']} до {slot['end_time']}\n\n"
        "Функция редактирования времени будет добавлена в следующем обновлении.\n"
        "Пока можете удалить слот и создать новый."
    )



def generate_cancellation_message(master_name: str, client_name: str, slot_time: str, location: str, reason: str) -> str:
    """Генерирует сообщение об отмене в стиле осьминога."""
    return (
        f"🌊 Печальные течения, {client_name}...\n\n"
        f"Мастер {master_name} вынужден отменить ваш сеанс:\n"
        f"🕐 {slot_time}\n"
        f"📍 {location}\n\n"
        f"💫 Причина: {reason}\n\n"
        f"Не расстраивайся! Глубины заповедника полны других возможностей для исцеления.\n"
        f"Найди нового мастера через команду /start 🐙✨"
    )

@with_rate_limiting
@with_error_handling
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение с кнопками выбора роли."""
    user_id = str(update.effective_user.id)
    
    # Логируем действие пользователя
    secure_log_user_action(logger, update.effective_user.id, "start_command")
    
    # Сбрасываем состояние пользователя
    user_states[user_id] = {"role": None, "awaiting": None}
    
    await update.message.reply_text(
        f"Привет, {update.effective_user.mention_html()}! 🐙\n\n"
        "Я мудрый Осьминог, хранитель этого места.\n"
        "Чтобы начать, выбери, кто ты:",
        reply_markup=get_main_keyboard(),
        parse_mode='HTML'
    )

@with_rate_limiting
@with_error_handling
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает все сообщения."""
    text = update.message.text
    user_id = str(update.effective_user.id)
    user_state = get_user_state(user_id)
    
    # Логируем активность пользователя
    secure_log_user_action(logger, update.effective_user.id, "message_received", text=text[:50])
    
    # Обновляем активность в health checker
    if health_checker:
        health_checker.update_last_activity()
    
    logger.info(f"Получено сообщение от {user_id}: '{text}', состояние: {user_state}")
    
    # Обрабатываем выбор роли
    if text == MASTER_ROLE:
        data = load_data()
        existing_master = None
        user_handle = f"@{update.effective_user.username}" if update.effective_user.username else None
        user_full_name = update.effective_user.full_name or ""
        
        # 1. Ищем по реальному ID (уже привязанные)
        logger.info(f"DEBUG: Ищем user_id={user_id} (тип: {type(user_id)}) среди мастеров...")
        for i, master in enumerate(data.get("masters", [])):
            master_id = master.get("telegram_id")
            logger.info(f"DEBUG: Мастер {i}: {master.get('name')} ID={master_id} (тип: {type(master_id)})")
            if master.get("telegram_id") == user_id:
                existing_master = master
                logger.info(f"DEBUG: НАЙДЕН мастер по ID: {master.get('name')}")
                break
        
        # 2. Если не найден, ищем по username (импортированные)
        if not existing_master and user_handle:
            for master in data.get("masters", []):
                if master.get("telegram_handle") == user_handle:
                    existing_master = master
                    # Привязываем реальный telegram_id к профилю
                    master["telegram_id"] = user_id
                    master["verified_at"] = datetime.now().isoformat()
                    save_data(data)
                    logger.info(f"Привязан telegram_id {user_id} к мастеру {master['name']} ({user_handle})")
                    break
        
        # 3. Если не найден, ищем по частичному совпадению имени
        potential_masters = []
        if not existing_master and user_full_name:
            for master in data.get("masters", []):
                master_name = master.get("name", "").lower()
                user_name_lower = user_full_name.lower()
                
                # Проверяем fake ID (не цифровой или короткий)
                telegram_id = master.get("telegram_id", "")
                is_fake_id = not (telegram_id.isdigit() and len(telegram_id) >= 8)
                
                if is_fake_id and (master_name in user_name_lower or user_name_lower in master_name):
                    potential_masters.append(master)
        
        if existing_master:
            await update.message.reply_text(
                f"О, {existing_master['name']}! Добро пожаловать обратно в заповедник! 🌊\n\n"
                f"Выбери, что хочешь сделать:",
                reply_markup=get_master_keyboard()
            )
            user_state["role"] = "master"
        elif potential_masters:
            # Предлагаем выбрать из потенциальных совпадений
            message = f"🔍 Возможно, ты один из этих мастеров?\n\n"
            
            for i, master in enumerate(potential_masters[:3], 1):  # Максимум 3 варианта
                name = master.get("name", "")
                handle = master.get("telegram_handle", "Нет @username")
                slots_count = len(master.get("time_slots", []))
                
                message += f"{i}. **{name}** ({handle}) - {slots_count} слотов\n"
            
            message += (
                f"\nОтветь цифрой (1, 2, 3) или:\n"
                f"• Напиши 'новый' для создания нового профиля\n"
                f"• Напиши 'нет' если это не ты\n\n"
                f"💡 Если твое имя {user_full_name} должно быть в списке, но его нет - "
                f"обратись к администратору @ivanslyozkin"
            )
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
            user_state["role"] = "master"
            user_state["awaiting"] = "select_existing_master"
            user_state["potential_masters"] = potential_masters
        else:
            # Предлагаем создать новый профиль или обратиться к админу
            await update.message.reply_text(
                f"🤔 Хм, мастера по имени '{user_full_name}' с @username '{user_handle}' "
                f"не найдено в базе заповедника.\n\n"
                f"Что делаем?\n\n"
                f"1️⃣ **Создать новый профиль** - напиши 'новый'\n"
                f"2️⃣ **Я уже есть в базе** - обратись к администратору @ivanslyozkin для привязки\n\n"
                f"💡 Возможно, твой @username не был указан в таблице мастеров",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove()
            )
            user_state["role"] = "master"
            user_state["awaiting"] = "new_or_existing_master"
        return
    
    elif text == CLIENT_ROLE:
        user_state["role"] = "client"
        
        # Проверяем, является ли пользователь владельцем девайса
        user_handle = f"@{update.effective_user.username}" if update.effective_user.username else None
        is_device_owner = user_handle == "@fshubin"  # Пока только Фил
        
        if is_device_owner:
            user_state["is_device_owner"] = True
            await update.message.reply_text(
                "🪑 Привет, Фил! Добро пожаловать в заповедник!\n\n"
                "Ты можешь управлять своим виброкреслом и смотреть обычные функции гостя:",
                reply_markup=get_device_owner_keyboard()
            )
        else:
            await update.message.reply_text(
                "Чудесно! Добро пожаловать в заповедник исцеления! 🌿\n\n"
                "Выбери, что хочешь сделать:",
                reply_markup=get_client_keyboard()
            )
        return
    
    # Обрабатываем профиль мастера
    if user_state.get("awaiting") == "master_profile":
        await process_master_profile(update, context)
        return
    
    # Обрабатываем выбор существующего мастера из списка
    if user_state.get("awaiting") == "select_existing_master":
        await process_select_existing_master(update, context)
        return
    
    # Обрабатываем выбор создания нового или обращения к админу
    if user_state.get("awaiting") == "new_or_existing_master":
        await process_new_or_existing_master(update, context)
        return
    
    # Обрабатываем новый профиль мастера
    if user_state.get("awaiting") == "new_profile":
        await process_new_profile(update, context)
        return
    
    # Обрабатываем причину отмены записи на виброкресло
    if user_state.get("awaiting") == "vibro_cancel_reason":
        await process_vibro_cancel_reason(update, context)
        return
    
    # Обрабатываем описание бага (но сначала проверяем что это не системная кнопка)
    if 'bug_report' in context.user_data:
        # Список системных кнопок, которые должны работать даже во время багрепорта
        system_buttons = [CHANGE_ROLE, BACK_TO_MENU, MASTER_ROLE, CLIENT_ROLE]
        
        if text not in system_buttons:
            await bug_reporter.handle_bug_description(update, context)
            return
        else:
            # Если это системная кнопка - очищаем состояние багрепорта и обрабатываем кнопку
            if 'bug_report' in context.user_data:
                del context.user_data['bug_report']
            # Продолжаем обработку кнопки ниже
    
    # Обрабатываем добавление слотов
    if user_state.get("awaiting") == "add_slots":
        await process_add_slots(update, context)
        return
    
    # Обрабатываем причину отклонения записи
    awaiting = user_state.get("awaiting") or ""
    if awaiting.startswith("decline_reason_"):
        await process_decline_reason(update, context)
        return
    
    # Обрабатываем кнопки мастера
    if user_state.get("role") == "master":
        await handle_master_buttons(update, context)
        return
    
    # Обрабатываем кнопки гостя
    if user_state.get("role") == "client":
        await handle_client_buttons(update, context)
        return
    
    # Общие кнопки
    if text == CHANGE_ROLE:
        await start(update, context)
        return
    
    # Неизвестная команда
    await update.message.reply_text(
        "Не понимаю этой команды. Используй /start чтобы начать заново."
    )

async def process_master_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает анкету мастера."""
    user_id = str(update.effective_user.id)
    profile_text = update.message.text
    user_name = update.effective_user.first_name or "Мастер"
    
    await update.message.reply_text(
        "Хм... позволь мне вглядеться в глубины твоих слов... 🐙"
    )
    
    # Обработка с GPT
    data = load_data()
    master_name = user_name
    
    # Используем GPT для анализа профиля и создания фэнтези-описания
    try:
        extracted_data, fantasy_description = gpt_service.process_master_profile(profile_text)
        
        # Обновляем имя, если GPT извлек его из профиля
        if extracted_data.get("name"):
            master_name = extracted_data["name"]
    except Exception as e:
        logger.error(f"Ошибка GPT обработки: {e}")
        # Fallback на базовое описание
        fantasy_description = f"В тёплых глубинах заповедника {master_name} делится древними знаниями исцеления. Его мудрые руки несут покой и восстановление."
        extracted_data = {
            "name": master_name,
            "services": ["массаж", "целительство"],
            "time_slots": [],
            "locations": ["Баня"]
        }
    
    # Сохраняем мастера
    new_master = {
        "telegram_id": user_id,
        "name": master_name,
        "original_description": profile_text,
        "fantasy_description": fantasy_description,
        "services": extracted_data.get("services", ["массаж", "целительство"]),
        "time_slots": extracted_data.get("time_slots", []),
        "is_active": True,
        "bookings": []
    }
    
    # Добавляем в список мастеров
    if "masters" not in data:
        data["masters"] = []
    data["masters"].append(new_master)
    save_data(data)
    
    response_text = (
        f"🌊 Глубины раскрыли мне твою суть, {master_name}!\n\n"
        f"**Твоё фэнтези-описание:**\n_{fantasy_description}_\n\n"
        f"**Твои услуги:** массаж, целительство\n"
        f"**Слотов создано:** 2\n\n"
        f"Теперь ты можешь управлять своим расписанием!"
    )
    
    await update.message.reply_text(
        response_text,
        reply_markup=get_master_keyboard(),
        parse_mode='Markdown'
    )
    
    # Сбрасываем состояние ожидания
    user_state = get_user_state(user_id)
    user_state["awaiting"] = None
    
    logger.info(f"Успешно зарегистрирован мастер {master_name} (ID: {user_id})")

async def process_select_existing_master(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выбор мастера из предложенного списка."""
    text = update.message.text.strip().lower()
    user_id = str(update.effective_user.id)
    user_state = get_user_state(user_id)
    
    potential_masters = user_state.get("potential_masters", [])
    
    if text in ['1', '2', '3'] and text.isdigit():
        choice_index = int(text) - 1
        
        if 0 <= choice_index < len(potential_masters):
            selected_master = potential_masters[choice_index]
            
            # Привязываем мастера к пользователю
            data = load_data()
            for master in data.get("masters", []):
                if master.get("name") == selected_master.get("name"):
                    master["telegram_id"] = user_id
                    master["verified_at"] = datetime.now().isoformat()
                    master["verification_method"] = "name_match"
                    save_data(data)
                    break
            
            await update.message.reply_text(
                f"🎉 Отлично! Добро пожаловать, {selected_master['name']}!\n\n"
                f"Твой профиль успешно привязан к этому аккаунту.\n"
                f"Теперь ты можешь управлять своими слотами!",
                reply_markup=get_master_keyboard()
            )
            
            user_state["role"] = "master"
            user_state["awaiting"] = None
            user_state.pop("potential_masters", None)
            
            logger.info(f"Мастер {selected_master['name']} привязан к {user_id} через выбор из списка")
            return
    
    elif text in ['новый', 'новая', 'new']:
        await update.message.reply_text(
            "Великолепно! Расскажи о себе в одном сообщении: имя, опыт, услуги "
            "и свободное время.",
            reply_markup=ReplyKeyboardRemove()
        )
        user_state["awaiting"] = "master_profile"
        user_state.pop("potential_masters", None)
        return
    
    elif text in ['нет', 'не я', 'no']:
        await update.message.reply_text(
            "Понятно! Тогда обратись к администратору @ivanslyozkin для "
            "ручной привязки твоего профиля или создай новый профиль, написав 'новый'.",
            reply_markup=ReplyKeyboardRemove()
        )
        user_state["awaiting"] = "new_or_existing_master"
        user_state.pop("potential_masters", None)
        return
    
    else:
        await update.message.reply_text(
            "Пожалуйста, ответь цифрой (1, 2, 3) или напиши 'новый' / 'нет'"
        )

async def process_new_or_existing_master(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выбор создания нового профиля или обращения к админу."""
    text = update.message.text.strip().lower()
    user_id = str(update.effective_user.id)
    user_state = get_user_state(user_id)
    
    if text in ['новый', 'новая', 'new', '1']:
        await update.message.reply_text(
            "Великолепно! Расскажи о себе в одном сообщении: имя, опыт, услуги "
            "и свободное время.",
            reply_markup=ReplyKeyboardRemove()
        )
        user_state["awaiting"] = "master_profile"
        return
    
    elif text in ['админ', 'администратор', 'помощь', 'admin', '2']:
        await update.message.reply_text(
            "💬 **Обратись к администратору:**\n\n"
            "Напиши @ivanslyozkin и укажи:\n"
            "• Твое имя в Telegram\n"
            "• Твое имя из таблицы мастеров\n"
            "• Твой @username\n\n"
            "Администратор поможет привязать твой профиль!\n\n"
            "Или напиши 'новый' для создания нового профиля.",
            parse_mode='Markdown'
        )
        return
    
    else:
        await update.message.reply_text(
            "Напиши 'новый' для создания нового профиля или 'админ' для обращения к администратору."
        )

async def handle_master_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопки мастера."""
    text = update.message.text
    user_id = str(update.effective_user.id)
    
    if text == MY_PROFILE:
        data = load_data()
        master = None
        for m in data.get("masters", []):
            if m.get("telegram_id") == user_id:
                master = m
                break
        
        if master:
            response = (
                f"👤 **Твой профиль, {master['name']}:**\n\n"
                f"🎭 **Фэнтези-описание:**\n{master['fantasy_description']}\n\n"
                f"📝 **Твои оригинальные слова:**\n{master['original_description']}\n\n"
                f"🛠 **Услуги:** {', '.join(master.get('services', []))}\n"
                f"⏰ **Слотов создано:** {len(master.get('time_slots', []))}"
            )
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text("Профиль не найден.")
    
    elif text == MY_SLOTS:
        data = load_data()
        master = None
        for m in data.get("masters", []):
            if m.get("telegram_id") == user_id:
                master = m
                break
        
        if master and master.get("time_slots"):
            await show_slots_with_management(update, context, master)
        else:
            await update.message.reply_text("У тебя пока нет слотов. Используй 'Добавить слоты'.")
    
    elif text == ADD_SLOTS:
        user_states[user_id] = {"role": "master", "awaiting": "add_slots"}
        await update.message.reply_text(
            "🐙 Расскажи, какие новые слоты хочешь добавить? Например:\n\n"
            "• 'Завтра с 14:00 до 18:00 в бане, каждый слот по 1 часу с перерывом по 10 минут между слотами'\n"
            "• 'В субботу в 18:00 на час в глэмпинге'\n"
            "• 'В понедельник с 12 до 15 в спасалке'\n\n"
            "Я пойму твой текст и создам нужные слоты! ✨"
        )
    
    elif text == EDIT_PROFILE:
        await edit_profile_request(update, context)
    
    elif text == VIEW_MASTERS:
        await show_masters_list(update, context)
    
    elif text == BACK_TO_MENU:
        await update.message.reply_text("Главное меню мастера:", reply_markup=get_master_keyboard())
    
    elif text == CHANGE_ROLE:
        await start(update, context)
    
    elif text == REPORT_BUG:
        await bug_reporter.handle_bug_report_start(update, context)
    
    elif text == MY_VIBRO_CHAIR:
        await show_vibro_chair_bookings(update, context)
    
    else:
        await update.message.reply_text("Используй кнопки меню для навигации.")

async def handle_client_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопки гостя."""
    text = update.message.text
    
    if text == VIEW_MASTERS:
        await show_masters_list(update, context)
    
    elif text == VIEW_DEVICES:
        await show_devices_list(update, context)
    
    elif text == VIEW_FREE_SLOTS:
        await show_free_slots_menu(update, context)
    
    elif text == MY_BOOKINGS:
        await show_client_bookings(update, context)
    
    elif text == BACK_TO_MENU:
        await update.message.reply_text("Главное меню гостя:", reply_markup=get_client_keyboard())
    
    elif text == CHANGE_ROLE:
        await start(update, context)
    
    elif text == REPORT_BUG:
        await bug_reporter.handle_bug_report_start(update, context)
    
    elif text == MY_VIBRO_CHAIR:
        await show_vibro_chair_bookings(update, context)
    
    else:
        await update.message.reply_text("Используй кнопки меню для навигации.")

def count_available_slots(master: dict) -> int:
    """Подсчитывает количество доступных слотов мастера (только будущие)."""
    from datetime import datetime
    
    slots = master.get("time_slots", [])
    bookings = master.get("bookings", [])
    
    # Получаем текущее время
    now = datetime.now()
    
    available_count = 0
    for slot in slots:
        slot_date = slot.get("date")
        slot_start_time = slot.get("start_time")
        
        if not slot_date or not slot_start_time:
            continue
            
        try:
            # Создаем datetime объект для сравнения
            slot_datetime = datetime.strptime(f"{slot_date} {slot_start_time}", "%Y-%m-%d %H:%M")
            
            # Показываем только будущие слоты (включая запас 30 минут)
            if slot_datetime <= now:
                continue
                
        except ValueError:
            # Если не можем распарсить время, пропускаем слот
            continue
            
        # Проверяем, не забронирован ли слот
        is_booked = any(
            booking.get("slot_date") == slot.get("date") and
            booking.get("slot_start_time") == slot.get("start_time") and
            booking.get("status") in ["pending", "confirmed"]
            for booking in bookings
        )
        if not is_booked:
            available_count += 1
    
    return available_count

async def show_client_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает записи клиента к мастерам."""
    user_id = str(update.effective_user.id)
    data = load_data()
    masters = data.get("masters", [])
    
    client_bookings = []
    
    # Ищем все записи клиента во всех мастерах
    for master in masters:
        for booking in master.get("bookings", []):
            if booking.get("client_id") == user_id:
                booking_info = {
                    "master_name": master.get("name", "Мастер"),
                    "master_id": master.get("telegram_id"),
                    "date": booking.get("slot_date"),
                    "start_time": booking.get("slot_start_time"),
                    "end_time": booking.get("slot_end_time"),
                    "location": booking.get("location"),
                    "status": booking.get("status"),
                    "booking": booking
                }
                client_bookings.append(booking_info)
    
    if not client_bookings:
        await update.message.reply_text(
            "📅 **Твои записи:**\n\n"
            "Пока у тебя нет записей к мастерам.",
            reply_markup=get_client_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    # Сортируем по дате и времени
    client_bookings.sort(key=lambda x: (x["date"], x["start_time"]))
    
    response = "📅 **Твои записи:**\n\n"
    
    for booking_info in client_bookings:
        status_icon = {
            "pending": "🕐",
            "confirmed": "✅", 
            "declined": "❌"
        }.get(booking_info["status"], "❓")
        
        status_text = {
            "pending": "Ожидает подтверждения",
            "confirmed": "Подтверждена", 
            "declined": "Отклонена"
        }.get(booking_info["status"], "Неизвестно")
        
        slot_text = f"{format_date_for_user(booking_info['date'])} с {booking_info['start_time']} до {booking_info['end_time']}"
        
        response += (
            f"{status_icon} **{booking_info['master_name']}**\n"
            f"📅 Время: {slot_text}\n"
            f"📍 Место: {booking_info['location']}\n"
            f"🔸 Статус: {status_text}\n\n"
        )
        
        # Если запись отклонена, показываем причину
        if booking_info["status"] == "declined":
            reason = booking_info["booking"].get("decline_reason", "Не указана")
            response += f"💬 Причина: {reason}\n\n"
    
    await update.message.reply_text(
        response,
        reply_markup=get_client_keyboard(),
        parse_mode='Markdown'
    )

async def show_masters_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список мастеров для клиентов с возможностью выбора."""
    data = load_data()
    masters = data.get("masters", [])
    
    # Определяем, это callback query или обычное сообщение
    if update.callback_query:
        await update.callback_query.answer()
        send_message = update.callback_query.message.reply_text
    else:
        send_message = update.message.reply_text
    
    if not masters:
        await send_message(
            "🌊 В заповеднике пока тишина... Ни одного мастера не зарегистрировано.",
            reply_markup=get_client_keyboard()
        )
        return
    
    await send_message(
        f"🐙 В заповеднике сейчас {len(masters)} мастеров готовы поделиться своими практиками:\n\n"
        "Выбери того, кто зовёт твою душу! ✨"
    )
    
    # Создаем inline кнопки для выбора мастера
    keyboard = []
    for master in masters:
        master_name = master.get('name', 'Мастер')
        # Подсчитываем доступные слоты
        available_slots = count_available_slots(master)
        
        if available_slots > 0:  # Показываем только мастеров с доступными слотами
            button_text = f"{master_name} ({available_slots} слотов)"
            callback_data = f"select_master_{master.get('telegram_id')}"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    if not keyboard:
        await send_message(
            "😔 Сейчас нет доступных слотов. Мастера заняты, но скоро освободятся!",
            reply_markup=get_client_keyboard()
        )
        return
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_client_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_message(
        "👇 Нажми на мастера, чтобы увидеть его слоты:",
        reply_markup=reply_markup
    )

async def show_master_details(update: Update, context: ContextTypes.DEFAULT_TYPE, master_id: str) -> None:
    """Показывает детали мастера и его доступные слоты."""
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    master = None
    for m in data.get("masters", []):
        if m.get("telegram_id") == master_id:
            master = m
            break
    
    if not master:
        await query.edit_message_text("Мастер не найден.")
        return
    
    # Показываем информацию о мастере
    info_text = (
        f"🐙 **{master.get('name', 'Мастер')}**\n\n"
        f"✨ **Заповедное описание:**\n{master.get('fantasy_description', 'Загадочная личность')}\n\n"
        f"📝 **Рассказ мастера:**\n{master.get('original_description', 'Без описания')}\n\n"
        f"🔮 **Практики:** {', '.join(master.get('services', ['массаж']))}\n\n"
        f"📅 **Доступные слоты:**"
    )
    
    await query.edit_message_text(info_text, parse_mode='Markdown')
    
    # Показываем доступные слоты
    from datetime import datetime
    slots = master.get("time_slots", [])
    bookings = master.get("bookings", [])
    now = datetime.now()
    
    available_slots = []
    for i, slot in enumerate(slots):
        # Проверяем, что слот еще не прошел по времени
        slot_date = slot.get("date")
        slot_start_time = slot.get("start_time")
        
        if not slot_date or not slot_start_time:
            continue
            
        try:
            slot_datetime = datetime.strptime(f"{slot_date} {slot_start_time}", "%Y-%m-%d %H:%M")
            if slot_datetime <= now:
                continue  # Пропускаем прошедшие слоты
        except ValueError:
            continue
        
        # Проверяем, не забронирован ли слот
        is_booked = any(
            booking.get("slot_date") == slot.get("date") and
            booking.get("slot_start_time") == slot.get("start_time") and
            booking.get("status") in ["pending", "confirmed"]
            for booking in bookings
        )
        if not is_booked:
            available_slots.append((i, slot))
    
    if not available_slots:
        await update.effective_chat.send_message(
            "😔 У этого мастера нет свободных слотов.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К списку мастеров", callback_data="back_to_masters")
            ]])
        )
        return
    
    # Создаем кнопки для доступных слотов
    keyboard = []
    for slot_index, slot in available_slots:
        slot_text = format_slot_for_user(slot)
        callback_data = f"book_slot_{master_id}_{slot_index}"
        keyboard.append([InlineKeyboardButton(f"📅 {slot_text}", callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("🔙 К списку мастеров", callback_data="back_to_masters")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message(
        "Выбери удобное время:",
        reply_markup=reply_markup
    )

async def process_booking_request(update: Update, context: ContextTypes.DEFAULT_TYPE, master_id: str, slot_index: str) -> None:
    """Обрабатывает запрос на бронирование."""
    query = update.callback_query
    await query.answer()
    
    client_id = str(update.effective_user.id)
    client_name = update.effective_user.first_name or "Гость"
    
    data = load_data()
    master = None
    for m in data.get("masters", []):
        if m.get("telegram_id") == master_id:
            master = m
            break
    
    if not master:
        await query.edit_message_text("Мастер не найден.")
        return
    
    try:
        slot_idx = int(slot_index)
        if slot_idx >= len(master.get("time_slots", [])):
            await query.edit_message_text("Слот не найден.")
            return
        
        slot = master["time_slots"][slot_idx]
    except (ValueError, IndexError):
        await query.edit_message_text("Неверный слот.")
        return
    
    # Проверяем ограничение: не более 2 записей к одному мастеру
    client_bookings_count = 0
    for booking in master.get("bookings", []):
        if booking.get("client_id") == client_id and booking.get("status") == "confirmed":
            client_bookings_count += 1
    
    if client_bookings_count >= 2:
        await query.edit_message_text(
            f"🚫 Осьминог мудро ограничивает: к мастеру {master.get('name')} можно записаться не более 2 раз за мероприятие.\n\n"
            f"Ты уже записан {client_bookings_count} раз(а). Попробуй других мастеров! 🐙",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К списку мастеров", callback_data="back_to_masters")
            ]])
        )
        return
    
    # Создаем заявку на бронирование
    booking = {
        "client_id": client_id,
        "client_name": client_name,
        "master_id": master_id,
        "master_name": master.get("name", "Мастер"),
        "slot_date": slot.get("date"),
        "slot_start_time": slot.get("start_time"),
        "slot_end_time": slot.get("end_time"),
        "location": slot.get("location"),
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    # Добавляем заявку
    if "bookings" not in master:
        master["bookings"] = []
    master["bookings"].append(booking)
    
    save_data(data)
    
    # Уведомляем клиента
    slot_text = format_slot_for_user(slot)
    await query.edit_message_text(
        f"✅ Заявка отправлена!\n\n"
        f"🐙 Мастер: {master.get('name')}\n"
        f"📅 Время: {slot_text}\n\n"
        f"Осьминог передал твою просьбу мастеру. Ожидай подтверждения! 🌊",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 К списку мастеров", callback_data="back_to_masters")
        ]])
    )
    
    # Уведомляем мастера
    try:
        booking_notification = (
            f"🔔 **Новая заявка на запись!**\n\n"
            f"👤 Гость: {client_name}\n"
            f"📅 Время: {slot_text}\n\n"
            f"Принять запись?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"confirm_booking_{len(master['bookings'])-1}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_booking_{len(master['bookings'])-1}")
            ]
        ]
        
        await application_instance.bot.send_message(
            chat_id=master_id,
            text=booking_notification,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления мастеру {master_id}: {e}")

def start_simple_webhook_server(telegram_app, port, main_loop=None):
    """Запускает простой HTTP сервер для webhook и health check"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading
    import json
    from datetime import datetime
    
    class WebhookHandler(BaseHTTPRequestHandler):
        event_loop = main_loop  # Сохраняем reference на main event loop
        def do_GET(self):
            if self.path == '/health':
                # Простой и быстрый healthcheck без внешних API вызовов
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "status": "ok", 
                    "timestamp": datetime.now().isoformat(),
                    "service": "mintoctopus_bot"
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                logger.info("✅ Health check запрос обработан")
            else:
                self.send_response(404)
                self.end_headers()
        
        def do_POST(self):
            if self.path == '/webhook':
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    post_data = self.rfile.read(content_length)
                    update_data = json.loads(post_data.decode('utf-8'))
                    
                    # Обрабатываем webhook
                    from telegram import Update
                    update = Update.de_json(update_data, telegram_app.bot)
                    
                    # Запускаем async функцию из другого thread
                    import asyncio
                    import threading
                    
                    # Запускаем coroutine в main loop из thread
                    if self.event_loop:
                        future = asyncio.run_coroutine_threadsafe(
                            telegram_app.process_update(update), 
                            self.event_loop
                        )
                        # Можно дождаться результата (опционально)
                        # future.result(timeout=5.0)
                    else:
                        logger.error("❌ Main event loop недоступен!")
                    
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'OK')
                    logger.info("✅ Webhook запрос обработан")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка webhook: {e}")
                    self.send_response(500)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Отключаем стандартные логи
    
    def run_server():
        server = HTTPServer(('0.0.0.0', port), WebhookHandler)
        server.timeout = 30  # Добавляем timeout для предотвращения зависаний
        logger.info(f"🌐 HTTP сервер запущен на порту {port}")
        try:
            server.serve_forever()
        except Exception as e:
            logger.error(f"❌ HTTP сервер ошибка: {e}")
            # Автоматический перезапуск сервера при ошибке
            run_server()
    
    # ДИАГНОСТИКА: Делаем thread НЕ daemon чтобы он держал процесс
    thread = threading.Thread(target=run_server, daemon=False)
    thread.start()
    logger.info(f"🚀 HTTP сервер поток запущен на порту {port} (НЕ daemon)")
    logger.info("🔍 HTTP thread будет держать процесс живым!")

def main() -> None:
    """Запускает бота."""
    global application_instance, health_checker
    
    telegram_token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")  # Backward compatibility
    if not telegram_token:
        logger.error("Не найден BOT_TOKEN. Убедись, что он есть в .env файле.")
        return

    # Инициализируем health checker
    health_checker = init_health_checker(telegram_token)
    
    application = Application.builder().token(telegram_token).build()
    application_instance = application  # Сохраняем для использования в напоминаниях

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test_reminder", test_reminder))
    application.add_handler(CommandHandler("bug", bug_reporter.handle_bug_report_start))
    
    # Админ команды
    application.add_handler(CommandHandler("pending_masters", admin_handlers.show_pending_masters))
    application.add_handler(CommandHandler("link_master", admin_handlers.link_master_manually))
    application.add_handler(CommandHandler("masters_status", admin_handlers.show_all_masters_status))
    application.add_handler(CommandHandler("admin_help", admin_handlers.help_admin))
    
    # Простая проверка админа по user_id
    def is_admin_user(user_id: int) -> bool:
        """Проверяет является ли пользователь админом"""
        admin_ids = [78273571]  # Твой user_id
        return user_id in admin_ids
    
    # Debug команда для проверки environment variables
    async def debug_env_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для проверки environment variables (только для админов)"""
        if not is_admin_user(update.effective_user.id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам.")
            return
        
        import os
        
        debug_info = []
        debug_info.append("🔍 ДИАГНОСТИКА ENVIRONMENT VARIABLES")
        debug_info.append("=" * 40)
        debug_info.append("")
        
        # Проверяем OpenAI API ключи
        openai_variants = [
            "OPENAI_API_KEY", "OPENAI_KEY", "OpenAI_API_Key", 
            "OPEN_AI_API_KEY", "openai_api_key", "GPT_API_KEY"
        ]
        
        found_keys = []
        debug_info.append("🔑 ПРОВЕРКА OPENAI API КЛЮЧЕЙ:")
        
        for variant in openai_variants:
            value = os.getenv(variant)
            if value:
                masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
                debug_info.append(f"✅ {variant}: {masked}")
                found_keys.append(variant)
            else:
                debug_info.append(f"❌ {variant}: НЕ НАЙДЕН")
        
        debug_info.append("")
        debug_info.append("🧪 ТЕСТ GPT SERVICE:")
        
        try:
            from services.gpt_service import GPTService
            gpt = GPTService()
            debug_info.append(f"✅ GPTService создан, fallback_mode: {gpt.fallback_mode}")
            
            if not gpt.fallback_mode:
                debug_info.append("🎉 GPT API доступен!")
                try:
                    test_result = gpt.parse_time_slots("завтра в 14")
                    if test_result:
                        debug_info.append(f"✅ Тест парсинга успешен!")
                    else:
                        debug_info.append(f"⚠️ Парсинг вернул пустой результат")
                except Exception as e:
                    debug_info.append(f"❌ Ошибка тестирования GPT: {str(e)[:100]}...")
            else:
                debug_info.append("⚠️ GPT работает в fallback режиме")
                
        except Exception as e:
            debug_info.append(f"❌ Ошибка создания GPTService: {e}")
        
        debug_info.append("")
        debug_info.append("📋 НАЙДЕННЫЕ КЛЮЧИ:")
        if found_keys:
            for key in found_keys:
                debug_info.append(f"   ✅ {key}")
        else:
            debug_info.append("   ❌ НИ ОДНОГО КЛЮЧА НЕ НАЙДЕНО")
        
        # Отправляем результат
        message = "\n".join(debug_info)
        
        # Разбиваем на части если длинный
        if len(message) > 4000:
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for part in parts:
                await update.message.reply_text(f"```\n{part}\n```", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"```\n{message}\n```", parse_mode='Markdown')
    
    # Простая команда диагностики без проверок админа
    async def simple_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Простая диагностика environment без admin проверки"""
        try:
            import os
            
            # Проверяем основные переменные
            bot_token = "НАЙДЕН" if os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") else "НЕ НАЙДЕН"
            openai_key = "НАЙДЕН" if os.getenv("OPENAI_API_KEY") else "НЕ НАЙДЕН"
            
            # Проверяем GPT Service
            try:
                from services.gpt_service import GPTService
                gpt = GPTService()
                gpt_status = f"Fallback: {gpt.fallback_mode}"
            except Exception as e:
                gpt_status = f"ОШИБКА: {str(e)[:50]}"
            
            message = f"""🔍 БЫСТРАЯ ДИАГНОСТИКА:
            
BOT_TOKEN: {bot_token}
OPENAI_API_KEY: {openai_key}
GPT_SERVICE: {gpt_status}

Время: {datetime.now().strftime('%H:%M:%S')}"""
            
            await update.message.reply_text(message)
            
        except Exception as e:
            await update.message.reply_text(f"Ошибка диагностики: {e}")
    
    application.add_handler(CommandHandler("debug_env", debug_env_command))
    application.add_handler(CommandHandler("diag", simple_debug))
    
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🐙 Рабочий осьминог v2.2.10-FORCE запущен и готов к работе!")
    logger.info("🔧 Доступны команды: /diag, /debug_env для диагностики")
    logger.info("🚀 Force deploy активирован - новые команды должны работать!")
    
    async def post_init(application):
        """Инициализация после запуска event loop."""
        scheduler.start()
        logger.info("📅 Планировщик напоминаний запущен!")
        
        # Запускаем aiohttp сервер для webhook и health check
        if os.getenv("ENVIRONMENT") == "production":
            port = int(os.getenv("PORT", 8080))
            logger.info(f"🌐 Запускаем простой HTTP сервер на порту {port}...")
            try:
                # Получаем текущий event loop
                current_loop = asyncio.get_running_loop()
                start_simple_webhook_server(application, port, current_loop)
                # Ждем чтобы сервер успел запуститься
                await asyncio.sleep(1)
                logger.info(f"✅ Простой HTTP сервер запущен на порту {port}!")
            except Exception as e:
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА запуска HTTP сервера: {e}")
                import traceback
                traceback.print_exc()
        else:
            logger.info("🔧 Development режим - webhook отключен")
    
    async def post_stop(application):
        """Очистка при остановке."""
        scheduler.shutdown()
        logger.info("📅 Планировщик напоминаний остановлен.")
    
    application.post_init = post_init
    application.post_stop = post_stop
    
    # Выбираем режим в зависимости от окружения
    if os.getenv("ENVIRONMENT") == "production":
        # Production: запускаем через webhook
        logger.info("🚀 Запускаем бот в production режиме (webhook)")
        
        async def run_production():
            # Запускаем application с webhook режимом
            import signal
            import asyncio
            
            stop_event = asyncio.Event()
            
            def signal_handler():
                logger.info("Получен сигнал остановки")
                stop_event.set()
            
            # Регистрируем обработчики сигналов
            loop = asyncio.get_event_loop()
            for sig in [signal.SIGTERM, signal.SIGINT]:
                loop.add_signal_handler(sig, signal_handler)
            
            try:
                # ДИАГНОСТИКА: Детальное логирование каждого шага
                logger.info("🔍 НАЧАЛО PRODUCTION STARTUP SEQUENCE")
                
                # Шаг 1: HTTP сервер
                try:
                    port = int(os.getenv("PORT", 8080))
                    logger.info(f"🚀 ШАГ 1: Запуск HTTP сервера на порту {port}...")
                    start_simple_webhook_server(application, port, asyncio.get_running_loop())
                    logger.info(f"✅ ШАГ 1: HTTP сервер запущен успешно!")
                except Exception as e:
                    logger.error(f"💥 ШАГ 1 ПРОВАЛЕН: HTTP сервер - {e}")
                    raise
                
                # Шаг 2: Пауза стабилизации
                try:
                    logger.info("⏰ ШАГ 2: Пауза стабилизации 2 секунды...")
                    await asyncio.sleep(2)
                    logger.info("✅ ШАГ 2: Пауза завершена")
                except Exception as e:
                    logger.error(f"💥 ШАГ 2 ПРОВАЛЕН: Пауза - {e}")
                    raise
                
                # Шаг 3: Telegram bot initialization
                try:
                    logger.info("🤖 ШАГ 3: Инициализация Telegram bot...")
                    await application.initialize()
                    logger.info("✅ ШАГ 3A: application.initialize() завершен")
                    
                    await application.start()
                    logger.info("✅ ШАГ 3B: application.start() завершен")
                    logger.info("✅ ШАГ 3: Telegram bot полностью инициализирован!")
                except Exception as e:
                    logger.error(f"💥 ШАГ 3 ПРОВАЛЕН: Telegram bot - {e}")
                    import traceback
                    logger.error(f"💥 ШАГ 3 TRACEBACK: {traceback.format_exc()}")
                    raise
                
                # Шаг 4: Планировщик
                try:
                    logger.info("📅 ШАГ 4: Запуск планировщика...")
                    scheduler.start()
                    logger.info("✅ ШАГ 4: Планировщик запущен успешно!")
                except Exception as e:
                    logger.error(f"💥 ШАГ 4 ПРОВАЛЕН: Планировщик - {e}")
                    import traceback
                    logger.error(f"💥 ШАГ 4 TRACEBACK: {traceback.format_exc()}")
                    # Планировщик не критичен, продолжаем
                
                logger.info("🎉 ВСЕ ШАГИ ЗАВЕРШЕНЫ! Приложение готово!")
                logger.info("⏳ Переход в режим ожидания...")
                
                # Шаг 5: Ожидание
                try:
                    await stop_event.wait()
                except Exception as e:
                    logger.error(f"💥 ШАГ 5 ПРОВАЛЕН: Ожидание - {e}")
                    raise
                
            finally:
                await application.stop()
                await application.shutdown()
        
        # Запускаем async функцию
        asyncio.run(run_production())
    else:
        # Development: используем polling
        logger.info("🔧 Запускаем бот в development режиме (polling)")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

# === ФУНКЦИИ ДЛЯ ПРОСМОТРА СВОБОДНЫХ СЛОТОВ ===

async def show_free_slots_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора даты для просмотра свободных слотов."""
    from datetime import datetime, timedelta
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    today = datetime.now().date()
    
    keyboard = [
        [InlineKeyboardButton("🌅 Сегодня", callback_data=f"slots_date_{today}")],
        [InlineKeyboardButton("🌄 Завтра", callback_data=f"slots_date_{today + timedelta(days=1)}")],
        [InlineKeyboardButton("📅 Послезавтра", callback_data=f"slots_date_{today + timedelta(days=2)}")],
        [InlineKeyboardButton("📆 Выбрать дату", callback_data="slots_custom_date")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_client_menu")]
    ]
    
    await update.message.reply_text(
        "📅 **Свободные слоты по времени**\n\n"
        "Выбери дату, чтобы увидеть всех доступных мастеров и оборудование:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_slots_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE, selected_date: str) -> None:
    """Показывает все свободные слоты на выбранную дату."""
    from datetime import datetime
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from collections import defaultdict
    
    data = load_data()
    masters = data.get("masters", [])
    bookings = data.get("bookings", [])
    
    # Группируем слоты по времени
    slots_by_time = defaultdict(list)
    
    for master in masters:
        if not master.get("is_active", True):
            continue
            
        for slot in master.get("time_slots", []):
            if slot.get("date") != selected_date:
                continue
            
            # Проверяем, что слот еще не прошел (для сегодняшней даты)
            slot_start_time = slot.get("start_time")
            if slot_start_time:
                try:
                    slot_datetime = datetime.strptime(f"{selected_date} {slot_start_time}", "%Y-%m-%d %H:%M")
                    if slot_datetime <= datetime.now():
                        continue  # Пропускаем прошедшие слоты
                except ValueError:
                    continue
            
            # Проверяем, не занят ли слот
            is_booked = any(
                booking.get("slot_date") == slot.get("date") and
                booking.get("slot_start_time") == slot.get("start_time") and
                booking.get("master_id") == master.get("telegram_id") and
                booking.get("status") in ["pending", "confirmed"]
                for booking in bookings
            )
            
            if not is_booked:
                time_key = f"{slot.get('start_time')}-{slot.get('end_time')}"
                slots_by_time[time_key].append({
                    'master': master,
                    'slot': slot
                })
    
    if not slots_by_time:
        await update.callback_query.edit_message_text(
            f"😔 На {selected_date} нет свободных слотов.\n\n"
            "Попробуй выбрать другую дату!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Выбрать другую дату", callback_data="slots_menu")]
            ])
        )
        return
    
    # Форматируем дату для отображения
    try:
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%A %d %B').replace('Monday', 'Понедельник').replace('Tuesday', 'Вторник').replace('Wednesday', 'Среда').replace('Thursday', 'Четверг').replace('Friday', 'Пятница').replace('Saturday', 'Суббота').replace('Sunday', 'Воскресенье')
    except:
        formatted_date = selected_date
    
    message = f"📅 **{formatted_date}**\n\n"
    keyboard = []
    
    # Сортируем по времени
    for time_range in sorted(slots_by_time.keys()):
        slots = slots_by_time[time_range]
        message += f"⏰ **{time_range}**\n"
        
        for slot_info in slots:
            master = slot_info['master']
            slot = slot_info['slot']
            
            if master.get('is_equipment'):
                # Это оборудование
                icon = "🪑"
                name = master.get('name', 'Оборудование')
            else:
                # Это мастер
                icon = "👤"
                name = master.get('name', 'Мастер')
            
            location = slot.get('location', 'Локация не указана')
            message += f"  {icon} {name} • {location}\n"
            
            # Добавляем кнопку для бронирования
            callback_data = f"book_time_{master.get('telegram_id')}_{slot.get('start_time')}_{selected_date}"
            keyboard.append([InlineKeyboardButton(
                f"{icon} {name} ({time_range})",
                callback_data=callback_data
            )])
        
        message += "\n"
    
    keyboard.append([InlineKeyboardButton("📅 Другая дата", callback_data="slots_menu")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_client_menu")])
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def process_time_booking_request(update: Update, context: ContextTypes.DEFAULT_TYPE, master_id: str, slot_time: str, slot_date: str) -> None:
    """Обрабатывает запрос на бронирование через выбор времени."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    import uuid
    
    query = update.callback_query
    user_id = str(query.from_user.id)
    data = load_data()
    
    # Находим мастера/оборудование
    master = None
    for m in data.get("masters", []):
        if m.get("telegram_id") == master_id:
            master = m
            break
    
    if not master:
        await query.edit_message_text("❌ Мастер или оборудование не найдено.")
        return
    
    # Находим конкретный слот
    target_slot = None
    for slot in master.get("time_slots", []):
        if (slot.get("date") == slot_date and 
            slot.get("start_time") == slot_time):
            target_slot = slot
            break
    
    if not target_slot:
        await query.edit_message_text("❌ Слот не найден.")
        return
    
    # Проверяем, не занят ли слот
    bookings = data.get("bookings", [])
    is_booked = any(
        booking.get("slot_date") == slot_date and
        booking.get("slot_start_time") == slot_time and
        booking.get("master_id") == master_id and
        booking.get("status") in ["pending", "confirmed"]
        for booking in bookings
    )
    
    if is_booked:
        await query.edit_message_text(
            "😔 Этот слот уже забронирован!\n\n"
            "Попробуй выбрать другое время.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Другие слоты", callback_data=f"slots_date_{slot_date}")]
            ])
        )
        return
    
    # Создаем бронирование
    booking_id = str(uuid.uuid4())[:8]
    
    booking = {
        "id": booking_id,
        "client_id": user_id,
        "client_name": query.from_user.first_name or "Гость",
        "master_id": master_id,
        "master_name": master.get("name", "Мастер"),
        "slot_date": slot_date,
        "slot_start_time": slot_time,
        "slot_end_time": target_slot.get("end_time"),
        "slot_location": target_slot.get("location", "Локация не указана"),
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "is_equipment": master.get("is_equipment", False)
    }
    
    data["bookings"].append(booking)
    save_data(data)
    
    # Определяем тип брони
    if master.get("is_equipment"):
        icon = "🪑"
        type_text = "оборудования"
        confirmation_text = "Твоя запись подтверждена автоматически!"
        # Для оборудования сразу подтверждаем
        booking["status"] = "confirmed"
        save_data(data)
    else:
        icon = "👤"
        type_text = "мастера"
        confirmation_text = "Мастер получил уведомление и скоро ответит."
        
        # Отправляем уведомление мастеру
        try:
            master_telegram_id = master.get("telegram_id")
            if master_telegram_id and master_telegram_id != "vibro_chair_virtual":
                confirmation_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{booking_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_booking_{booking_id}")
                    ]
                ])
                
                await context.bot.send_message(
                    chat_id=int(master_telegram_id),
                    text=(
                        f"🔔 **Новая запись!**\n\n"
                        f"👤 Гость: {booking['client_name']}\n"
                        f"📅 Дата: {booking['slot_date']}\n"
                        f"⏰ Время: {booking['slot_start_time']} - {booking['slot_end_time']}\n"
                        f"📍 Локация: {booking['slot_location']}\n\n"
                        f"Подтвердить запись?"
                    ),
                    reply_markup=confirmation_keyboard,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления мастеру: {e}")
    
    # Уведомляем клиента
    await query.edit_message_text(
        f"✅ **Запись создана!**\n\n"
        f"{icon} {type_text.title()}: {master.get('name')}\n"
        f"📅 Дата: {slot_date}\n"
        f"⏰ Время: {slot_time} - {target_slot.get('end_time')}\n"
        f"📍 Локация: {target_slot.get('location')}\n\n"
        f"{confirmation_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_client_menu")]
        ]),
        parse_mode='Markdown'
    )
    
    # Если это оборудование, планируем напоминание
    if master.get("is_equipment"):
        schedule_reminder(booking, is_equipment=True)

# === ФУНКЦИИ ДЛЯ ДЕВАЙСОВ ЗАПОВЕДНИКА ===

async def show_devices_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список девайсов заповедника."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    data = load_data()
    devices = data.get("devices", [])
    
    if not devices:
        # Для callback queries используем edit_message_text
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "😔 Пока нет доступных девайсов в заповеднике."
            )
        else:
            await update.message.reply_text(
                "😔 Пока нет доступных девайсов в заповеднике.",
                reply_markup=get_client_keyboard()
            )
        return
    
    message = "🔬 **Девайсы заповедника**\n\n"
    message += "Выбери устройство чтобы узнать подробности и забронировать:\n\n"
    
    keyboard = []
    
    for device in devices:
        if not device.get("is_active", True):
            continue
            
        icon = device.get("icon", "🔧")
        name = device.get("name", "Устройство")
        location = device.get("location", "Заповедник")
        
        # Подсчитываем доступные слоты
        total_slots = len(device.get("time_slots", []))
        booked_slots = sum(1 for slot in device.get("time_slots", []) if slot.get("is_booked", False))
        available_slots = total_slots - booked_slots
        
        button_text = f"{icon} {name} • {location} ({available_slots} слотов)"
        callback_data = f"device_info_{device.get('id')}"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Добавляем краткое описание в сообщение
        message += f"{icon} **{name}**\n"
        message += f"📍 {location}\n"
        message += f"⏰ Доступно слотов: {available_slots}\n\n"
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_client_menu")])
    
    # Для callback queries используем edit_message_text
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def show_device_details(update: Update, context: ContextTypes.DEFAULT_TYPE, device_id: str) -> None:
    """Показывает подробную информацию о девайсе."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    data = load_data()
    devices = data.get("devices", [])
    
    device = None
    for d in devices:
        if d.get("id") == device_id:
            device = d
            break
    
    if not device:
        # Детальное логирование для отладки
        logger.error(f"Device not found in show_device_details - device_id: '{device_id}', available devices: {[d.get('id') for d in devices]}")
        await update.callback_query.edit_message_text("❌ Устройство не найдено. Попробуй обновить список.")
        return
    
    icon = device.get("icon", "🔧")
    name = device.get("name", "Устройство")
    location = device.get("location", "Заповедник")
    description = device.get("description", "Описание отсутствует")
    
    # Информация о времени работы
    working_hours = device.get("working_hours", {})
    if working_hours.get("start") == "00:00" and working_hours.get("end") == "23:59":
        time_info = "⏰ Доступно: **круглосуточно**"
    else:
        time_info = f"⏰ Время работы: **{working_hours.get('start', '?')} - {working_hours.get('end', '?')}**"
    
    session_duration = device.get("session_duration", 60)
    
    # Собираем сообщение
    message = f"{icon} **{name}**\n"
    message += f"📍 **Локация:** {location}\n"
    message += f"{time_info}\n"
    message += f"⏱️ **Длительность сеанса:** {session_duration} мин\n\n"
    
    message += f"📖 **Описание:**\n{description}\n\n"
    
    # Инструкции
    instructions = device.get("instructions", [])
    if instructions:
        message += "📋 **Как пользоваться:**\n"
        for i, instruction in enumerate(instructions, 1):
            message += f"{i}. {instruction}\n"
        message += "\n"
    
    # Информация о локации (для кресла)
    location_info = device.get("location_info")
    if location_info:
        message += "📍 **О локации:**\n"
        message += f"{location_info}\n\n"
    
    # После использования (для других девайсов)
    after_use = device.get("after_use", [])
    if after_use:
        message += "✅ **После сеанса:**\n"
        for instruction in after_use:
            message += f"• {instruction}\n"
        message += "\n"
    
    # Предупреждения
    warnings = device.get("warnings", [])
    if warnings:
        message += "⚠️ **Внимание:**\n"
        for warning in warnings:
            message += f"• {warning}\n"
        message += "\n"
    
    # Кнопки
    keyboard = [
        [InlineKeyboardButton("📅 Забронировать", callback_data=f"book_device_{device_id}")],
        [InlineKeyboardButton("⬅️ К списку девайсов", callback_data="devices_list")]
    ]
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_device_booking_slots(update: Update, context: ContextTypes.DEFAULT_TYPE, device_id: str) -> None:
    """Показывает доступные слоты для бронирования девайса."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from datetime import datetime, timedelta
    
    data = load_data()
    devices = data.get("devices", [])
    device_bookings = data.get("device_bookings", [])
    
    device = None
    for d in devices:
        if d.get("id") == device_id:
            device = d
            break
    
    if not device:
        logger.error(f"Device not found - device_id: '{device_id}', function: show_device_booking_slots")
        await update.callback_query.edit_message_text("❌ Устройство не найдено. Попробуй обновить список.")
        return
    
    icon = device.get("icon", "🔧")
    name = device.get("name", "Устройство")
    
    # Показываем слоты на ближайшие дни
    today = datetime.now().date()
    message = f"{icon} **{name}**\n\n📅 Выбери удобное время:\n\n"
    
    keyboard = []
    slots_found = False
    
    # Группируем слоты по дням
    for day_offset in range(3):  # Показываем 3 дня
        check_date = today + timedelta(days=day_offset)
        date_str = check_date.strftime('%Y-%m-%d')
        
        day_slots = []
        for slot in device.get("time_slots", []):
            if slot.get("date") == date_str and not slot.get("is_booked", False):
                # Проверяем что слот не забронирован в device_bookings
                is_booked_in_bookings = any(
                    booking.get("device_id") == device_id and
                    booking.get("slot_date") == date_str and
                    booking.get("slot_start_time") == slot.get("start_time") and
                    booking.get("status") in ["pending", "confirmed"]
                    for booking in device_bookings
                )
                
                if not is_booked_in_bookings:
                    day_slots.append(slot)
        
        if day_slots:
            # Название дня
            if day_offset == 0:
                day_name = "Сегодня"
            elif day_offset == 1:
                day_name = "Завтра"
            else:
                day_name = check_date.strftime('%A').replace('Monday', 'Понедельник').replace('Tuesday', 'Вторник').replace('Wednesday', 'Среда').replace('Thursday', 'Четверг').replace('Friday', 'Пятница').replace('Saturday', 'Суббота').replace('Sunday', 'Воскресенье')
            
            keyboard.append([InlineKeyboardButton(
                f"📅 {day_name} ({len(day_slots)} слотов)",
                callback_data=f"device_slots_{device_id}_{date_str}"
            )])
            slots_found = True
    
    if not slots_found:
        message += "😔 Нет доступных слотов на ближайшие дни.\n"
        message += "Попробуй позже или выбери другое устройство."
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад к устройству", callback_data=f"device_info_{device_id}")])
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_device_day_slots(update: Update, context: ContextTypes.DEFAULT_TYPE, device_id: str, date_str: str) -> None:
    """Показывает слоты девайса на конкретный день."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from datetime import datetime
    import uuid
    
    data = load_data()
    devices = data.get("devices", [])
    device_bookings = data.get("device_bookings", [])
    
    device = None
    for d in devices:
        if d.get("id") == device_id:
            device = d
            break
    
    if not device:
        logger.error(f"Device not found - device_id: '{device_id}', function: show_device_booking_slots")
        await update.callback_query.edit_message_text("❌ Устройство не найдено. Попробуй обновить список.")
        return
    
    icon = device.get("icon", "🔧")
    name = device.get("name", "Устройство")
    
    # Форматируем дату
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%A %d %B').replace('Monday', 'Понедельник').replace('Tuesday', 'Вторник').replace('Wednesday', 'Среда').replace('Thursday', 'Четверг').replace('Friday', 'Пятница').replace('Saturday', 'Суббота').replace('Sunday', 'Воскресенье')
    except:
        formatted_date = date_str
    
    message = f"{icon} **{name}**\n📅 **{formatted_date}**\n\n"
    
    # Находим свободные слоты на этот день
    available_slots = []
    for slot in device.get("time_slots", []):
        if slot.get("date") == date_str and not slot.get("is_booked", False):
            # Проверяем что слот не забронирован в device_bookings
            is_booked_in_bookings = any(
                booking.get("device_id") == device_id and
                booking.get("slot_date") == date_str and
                booking.get("slot_start_time") == slot.get("start_time") and
                booking.get("status") in ["pending", "confirmed"]
                for booking in device_bookings
            )
            
            if not is_booked_in_bookings:
                available_slots.append(slot)
    
    if not available_slots:
        message += "😔 Нет свободных слотов на этот день."
        keyboard = [[InlineKeyboardButton("⬅️ Выбрать другой день", callback_data=f"book_device_{device_id}")]]
    else:
        message += "⏰ Доступные слоты:\n\n"
        keyboard = []
        
        for slot in sorted(available_slots, key=lambda x: x.get("start_time", "")):
            start_time = slot.get("start_time", "")
            end_time = slot.get("end_time", "")
            
            button_text = f"🕐 {start_time} - {end_time}"
            callback_data = f"confirm_device_booking_{device_id}_{date_str}_{start_time}"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            message += f"• {start_time} - {end_time}\n"
        
        keyboard.append([InlineKeyboardButton("⬅️ Выбрать другой день", callback_data=f"book_device_{device_id}")])
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def process_device_booking(update: Update, context: ContextTypes.DEFAULT_TYPE, device_id: str, date_str: str, start_time: str) -> None:
    """Обрабатывает бронирование девайса."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    import uuid
    from datetime import datetime
    
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    data = load_data()
    devices = data.get("devices", [])
    device_bookings = data.get("device_bookings", [])
    
    # Находим девайс
    device = None
    for d in devices:
        if d.get("id") == device_id:
            device = d
            break
    
    if not device:
        logger.error(f"Device not found - device_id: '{device_id}', function: process_device_booking")
        await query.edit_message_text("❌ Устройство не найдено. Попробуй обновить список.")
        return
    
    # Находим конкретный слот
    target_slot = None
    for slot in device.get("time_slots", []):
        if (slot.get("date") == date_str and 
            slot.get("start_time") == start_time):
            target_slot = slot
            break
    
    if not target_slot:
        await query.edit_message_text("❌ Слот не найден.")
        return
    
    # Проверяем, не занят ли слот
    is_booked = any(
        booking.get("device_id") == device_id and
        booking.get("slot_date") == date_str and
        booking.get("slot_start_time") == start_time and
        booking.get("status") in ["pending", "confirmed"]
        for booking in device_bookings
    )
    
    if is_booked:
        await query.edit_message_text(
            "😔 Этот слот уже забронирован!\n\n"
            "Попробуй выбрать другое время.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Другие слоты", callback_data=f"book_device_{device_id}")]
            ])
        )
        return
    
    # Создаем бронирование девайса
    booking_id = str(uuid.uuid4())[:8]
    
    device_booking = {
        "id": booking_id,
        "client_id": user_id,
        "client_name": query.from_user.first_name or "Гость",
        "device_id": device_id,
        "device_name": device.get("name", "Устройство"),
        "slot_date": date_str,
        "slot_start_time": start_time,
        "slot_end_time": target_slot.get("end_time"),
        "slot_location": device.get("location", "Заповедник"),
        "status": "confirmed",  # Девайсы автоподтверждаются
        "created_at": datetime.now().isoformat(),
        "is_device": True
    }
    
    # Добавляем бронирование
    if "device_bookings" not in data:
        data["device_bookings"] = []
    
    data["device_bookings"].append(device_booking)
    
    # Помечаем слот как забронированный
    for slot in device.get("time_slots", []):
        if (slot.get("date") == date_str and 
            slot.get("start_time") == start_time):
            slot["is_booked"] = True
            break
    
    save_data(data)
    
    icon = device.get("icon", "🔧")
    session_duration = device.get("session_duration", 60)
    
    # Уведомляем клиента
    await query.edit_message_text(
        f"✅ **Девайс забронирован!**\n\n"
        f"{icon} **{device.get('name')}**\n"
        f"📅 Дата: {date_str}\n"
        f"⏰ Время: {start_time} - {target_slot.get('end_time')}\n"
        f"📍 Локация: {device.get('location')}\n"
        f"⏱️ Длительность: {session_duration} мин\n\n"
        f"🎉 **Запись подтверждена автоматически!**\n"
        f"⏰ Напоминание придёт за 15 минут до сеанса.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
            [InlineKeyboardButton("🔬 Другие девайсы", callback_data="devices_list")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_client_menu")]
        ]),
        parse_mode='Markdown'
    )
    
    # Планируем напоминание для девайса
    schedule_reminder(device_booking, is_equipment=True)
    
    # Уведомляем Фила о новой записи на виброкресло
    if device_id == "vibro_chair":
        await notify_device_owner_about_booking(context, device_booking)

if __name__ == "__main__":
    main()

async def show_vibro_chair_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает все записи на виброкресло для владельца (Фила)."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from datetime import datetime, timedelta
    
    data = load_data()
    device_bookings = data.get("device_bookings", [])
    
    # Фильтруем записи только на виброкресло
    vibro_bookings = [
        booking for booking in device_bookings 
        if booking.get("device_id") == "vibro_chair"
    ]
    
    if not vibro_bookings:
        await update.message.reply_text(
            "🪑 **Мое виброкресло**\n\n"
            "📅 Пока нет записей на виброкресло.\n"
            "Когда кто-то запишется, ты увидишь их здесь!",
            parse_mode='Markdown',
            reply_markup=get_device_owner_keyboard()
        )
        return
    
    # Группируем записи по дням
    today = datetime.now().date()
    bookings_by_date = {}
    
    for booking in vibro_bookings:
        booking_date = booking.get("slot_date")
        if booking_date not in bookings_by_date:
            bookings_by_date[booking_date] = []
        bookings_by_date[booking_date].append(booking)
    
    # Формируем сообщение
    message = "🪑 **Мое виброкресло**\n\n"
    message += f"📅 Всего записей: {len(vibro_bookings)}\n\n"
    
    # Сортируем по датам
    sorted_dates = sorted(bookings_by_date.keys())
    
    keyboard = []
    
    for date_str in sorted_dates:
        date_bookings = bookings_by_date[date_str]
        # Парсим дату
        try:
            booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if booking_date == today:
                day_label = "Сегодня"
            elif booking_date == today + timedelta(days=1):
                day_label = "Завтра"
            else:
                day_label = booking_date.strftime("%d.%m")
        except:
            day_label = date_str
        
        message += f"📅 **{day_label} ({date_str})** - {len(date_bookings)} записей:\n"
        
        for booking in sorted(date_bookings, key=lambda x: x.get("slot_start_time", "")):
            start_time = booking.get("slot_start_time", "")
            end_time = booking.get("slot_end_time", "")
            guest_name = booking.get("guest_username", "") or booking.get("guest_name", "Гость")
            
            message += f"🕐 {start_time}-{end_time} — {guest_name}\n"
            
            # Добавляем кнопку отмены для каждой записи
            booking_id = booking.get("id", "")
            if booking_id:
                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ Отменить {start_time} {guest_name[:10]}",
                        callback_data=f"cancel_vibro_{booking_id}"
                    )
                ])
        
        message += "\n"
    
    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_device_menu")])
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_vibro_booking_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE, booking_id: str) -> None:
    """Обрабатывает отмену записи на виброкресло."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    query = update.callback_query
    await query.answer()
    
    # Находим запись по ID
    data = load_data()
    device_bookings = data.get("device_bookings", [])
    
    booking = None
    for b in device_bookings:
        if b.get("id") == booking_id:
            booking = b
            break
    
    if not booking:
        await query.edit_message_text(
            "❌ Запись не найдена. Возможно, она уже была отменена.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_device_menu")]
            ])
        )
        return
    
    # Получаем информацию о записи
    guest_name = booking.get("guest_username", "") or booking.get("guest_name", "Гость")
    start_time = booking.get("slot_start_time", "")
    end_time = booking.get("slot_end_time", "")
    slot_date = booking.get("slot_date", "")
    
    # Сохраняем ID записи для обработки причины отмены
    user_id = str(query.from_user.id)
    user_states[user_id] = {
        "role": "client", 
        "is_device_owner": True,
        "awaiting": "vibro_cancel_reason",
        "cancel_booking_id": booking_id
    }
    
    await query.edit_message_text(
        f"❌ **Отмена записи на виброкресло**\n\n"
        f"📅 Дата: {slot_date}\n"
        f"🕐 Время: {start_time}-{end_time}\n"
        f"👤 Клиент: {guest_name}\n\n"
        f"🖊️ **Укажи причину отмены:**\n"
        f"(Эта причина будет отправлена клиенту)\n\n"
        f"Напиши причину следующим сообщением ⬇️",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Отменить отмену", callback_data="back_to_device_menu")]
        ]),
        parse_mode='Markdown'
    )

async def process_vibro_cancel_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает причину отмены записи на виброкресло."""
    user_id = str(update.effective_user.id)
    user_state = user_states.get(user_id, {})
    
    cancel_reason = update.message.text
    booking_id = user_state.get("cancel_booking_id")
    
    if not booking_id:
        await update.message.reply_text(
            "❌ Ошибка: не найден ID записи для отмены.",
            reply_markup=get_device_owner_keyboard()
        )
        return
    
    # Находим и отменяем запись
    data = load_data()
    device_bookings = data.get("device_bookings", [])
    
    booking = None
    booking_index = None
    for i, b in enumerate(device_bookings):
        if b.get("id") == booking_id:
            booking = b
            booking_index = i
            break
    
    if not booking:
        await update.message.reply_text(
            "❌ Запись не найдена в базе данных.",
            reply_markup=get_device_owner_keyboard()
        )
        return
    
    # Получаем информацию о записи для уведомления
    guest_id = booking.get("guest_id")
    guest_name = booking.get("guest_username", "") or booking.get("guest_name", "Гость")
    start_time = booking.get("slot_start_time", "")
    end_time = booking.get("slot_end_time", "")
    slot_date = booking.get("slot_date", "")
    device_name = "Виброакустическое кресло"
    
    # Удаляем запись из device_bookings
    device_bookings.pop(booking_index)
    
    # Освобождаем слот в устройстве
    devices = data.get("devices", [])
    for device in devices:
        if device.get("id") == "vibro_chair":
            for slot in device.get("time_slots", []):
                if (slot.get("date") == slot_date and 
                    slot.get("start_time") == start_time):
                    slot["is_booked"] = False
                    break
            break
    
    save_data(data)
    
    # Очищаем состояние пользователя
    user_states[user_id] = {"role": "client", "is_device_owner": True}
    
    # Уведомляем клиента об отмене
    if guest_id:
        try:
            await context.bot.send_message(
                chat_id=guest_id,
                text=f"❌ **Запись отменена**\n\n"
                     f"🪑 **{device_name}**\n"
                     f"📅 Дата: {slot_date}\n"
                     f"🕐 Время: {start_time}-{end_time}\n\n"
                     f"📝 **Причина отмены:**\n{cancel_reason}\n\n"
                     f"Извини за неудобства! Ты можешь записаться на другое время.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление об отмене клиенту {guest_id}: {e}")
    
    # Подтверждаем отмену Филу
    await update.message.reply_text(
        f"✅ **Запись успешно отменена!**\n\n"
        f"📅 Дата: {slot_date}\n"
        f"🕐 Время: {start_time}-{end_time}\n"
        f"👤 Клиент: {guest_name}\n"
        f"📝 Причина: {cancel_reason}\n\n"
        f"{'📱 Клиент уведомлен' if guest_id else '⚠️ Не удалось уведомить клиента'}\n"
        f"🪑 Слот снова доступен для записи.",
        reply_markup=get_device_owner_keyboard(),
        parse_mode='Markdown'
    )

async def notify_device_owner_about_booking(context: ContextTypes.DEFAULT_TYPE, device_booking: dict) -> None:
    """Уведомляет владельца девайса о новой записи."""
    device_id = device_booking.get("device_id")
    
    # Пока только для виброкресла Фила
    if device_id != "vibro_chair":
        return
    
    # ID Фила @fshubin - нужно будет получить из реальной системы
    phil_id = None
    
    # Находим Фила в базе данных
    data = load_data()
    masters = data.get("masters", [])
    
    # Ищем @fshubin среди мастеров или пользователей
    for master in masters:
        if master.get("telegram_handle") == "@fshubin":
            phil_id = master.get("telegram_id")
            break
    
    # Если не нашли среди мастеров, можно использовать hardcoded ID
    # Это временное решение, пока Фил не зарегистрируется через бота
    if not phil_id:
        # Здесь можно добавить hardcoded telegram_id Фила если известен
        logger.warning("Не найден telegram_id для @fshubin, уведомление не отправлено")
        return
    
    # Формируем уведомление
    guest_name = device_booking.get("guest_username", "") or device_booking.get("guest_name", "Гость")
    start_time = device_booking.get("slot_start_time", "")
    end_time = device_booking.get("slot_end_time", "")
    slot_date = device_booking.get("slot_date", "")
    
    try:
        await context.bot.send_message(
            chat_id=phil_id,
            text=f"🪑 **Новая запись на виброкресло!**\n\n"
                 f"👤 **Клиент:** {guest_name}\n"
                 f"📅 **Дата:** {slot_date}\n"
                 f"🕐 **Время:** {start_time}-{end_time}\n\n"
                 f"📋 Для управления записями используй кнопку 'Мое виброкресло 🪑' в боте.",
            parse_mode='Markdown'
        )
        logger.info(f"Уведомление о записи на виброкресло отправлено Филу (ID: {phil_id})")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление Филу (ID: {phil_id}): {e}")