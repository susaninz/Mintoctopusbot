"""
Клавиатуры для Telegram бота
"""
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from bot.constants import (
    MASTER_ROLE, CLIENT_ROLE, MY_SLOTS, ADD_SLOTS, MY_PROFILE, EDIT_PROFILE,
    VIEW_MASTERS, VIEW_DEVICES, VIEW_FREE_SLOTS, MY_BOOKINGS, BACK_TO_MENU, CHANGE_ROLE
)


def get_role_selection_keyboard() -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру выбора роли.
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура с выбором роли
    """
    return ReplyKeyboardMarkup(
        [[MASTER_ROLE, CLIENT_ROLE]], 
        resize_keyboard=True, 
        one_time_keyboard=True
    )


def get_master_keyboard() -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру для мастера.
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура мастера
    """
    return ReplyKeyboardMarkup([
        [MY_SLOTS, ADD_SLOTS],
        [MY_PROFILE, EDIT_PROFILE],
        [CHANGE_ROLE, BACK_TO_MENU]
    ], resize_keyboard=True)


def get_client_keyboard() -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру для клиента.
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура клиента
    """
    return ReplyKeyboardMarkup([
        [VIEW_MASTERS, VIEW_DEVICES],
        [VIEW_FREE_SLOTS, MY_BOOKINGS],
        [CHANGE_ROLE]
    ], resize_keyboard=True)


def create_slot_management_keyboard(slots: list) -> InlineKeyboardMarkup:
    """
    Создает inline клавиатуру для управления слотами.
    
    Args:
        slots: Список слотов мастера
        
    Returns:
        InlineKeyboardMarkup: Inline клавиатура
    """
    keyboard = []
    
    for i, slot in enumerate(slots):
        date = slot.get("date", "")
        start_time = slot.get("start_time", "")
        end_time = slot.get("end_time", "")
        location = slot.get("location", "")
        
        slot_text = f"{date} {start_time}-{end_time} ({location})"
        callback_data = f"delete_slot_{i}"
        
        keyboard.append([InlineKeyboardButton(
            f"❌ {slot_text}", 
            callback_data=callback_data
        )])
    
    return InlineKeyboardMarkup(keyboard)


def create_master_selection_keyboard(masters: list) -> InlineKeyboardMarkup:
    """
    Создает inline клавиатуру для выбора мастера.
    
    Args:
        masters: Список мастеров
        
    Returns:
        InlineKeyboardMarkup: Inline клавиатура
    """
    keyboard = []
    
    for master in masters:
        master_id = master.get("telegram_id", "")
        name = master.get("name", "Мастер")
        
        # Подсчитываем доступные слоты
        available_slots = count_available_slots(master)
        
        button_text = f"{name} (🟢 {available_slots} слотов)"
        callback_data = f"select_master_{master_id}"
        
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=callback_data
        )])
    
    return InlineKeyboardMarkup(keyboard)


def create_booking_slots_keyboard(slots: list, master_id: str) -> InlineKeyboardMarkup:
    """
    Создает inline клавиатуру для бронирования слотов.
    
    Args:
        slots: Доступные слоты
        master_id: ID мастера
        
    Returns:
        InlineKeyboardMarkup: Inline клавиатура
    """
    keyboard = []
    
    for i, slot in enumerate(slots):
        date = slot.get("date", "")
        start_time = slot.get("start_time", "")
        end_time = slot.get("end_time", "")
        location = slot.get("location", "")
        
        slot_text = f"{date} {start_time}-{end_time} • {location}"
        callback_data = f"book_slot_{master_id}_{i}"
        
        keyboard.append([InlineKeyboardButton(
            f"📅 {slot_text}",
            callback_data=callback_data
        )])
    
    # Кнопка "Назад к списку мастеров"
    keyboard.append([InlineKeyboardButton(
        "⬅️ Назад к мастерам",
        callback_data="back_to_masters"
    )])
    
    return InlineKeyboardMarkup(keyboard)


def create_booking_confirmation_keyboard(booking_id: str) -> InlineKeyboardMarkup:
    """
    Создает inline клавиатуру для подтверждения бронирования мастером.
    
    Args:
        booking_id: ID бронирования
        
    Returns:
        InlineKeyboardMarkup: Inline клавиатура
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{booking_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_{booking_id}")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def count_available_slots(master: dict) -> int:
    """
    Подсчитывает количество доступных слотов мастера (только будущие).
    
    Args:
        master: Данные мастера
        
    Returns:
        int: Количество доступных слотов
    """
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
            
            # Показываем только будущие слоты
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