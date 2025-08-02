"""
Константы для Octopus Concierge Bot
"""

# === КНОПКИ ИНТЕРФЕЙСА ===
MASTER_ROLE = "Я мну 🐙"
CLIENT_ROLE = "Хочу, чтобы меня помяли 🙏"

# Кнопки для мастеров
MY_SLOTS = "Мои слоты 📋"
ADD_SLOTS = "Добавить слоты ➕"
MY_PROFILE = "Мой профиль 👤"
EDIT_PROFILE = "Редактировать профиль ✏️"

# Кнопки для гостей
VIEW_MASTERS = "Мастера 👥"
VIEW_DEVICES = "Девайсы заповедника 🔬"
VIEW_FREE_SLOTS = "Свободные слоты 📅"
MY_BOOKINGS = "Мои записи 📋"

# Общие кнопки
BACK_TO_MENU = "Главное меню 🏠"
CHANGE_ROLE = "Сменить роль 🔄"
REPORT_BUG = "Сообщить о проблеме 🐛"

# === ВРЕМЕННЫЕ КОНСТАНТЫ ===
REMINDER_MINUTES_BEFORE = 15
DEFAULT_SLOT_DURATION_MINUTES = 60
MAX_BOOKINGS_PER_MASTER = 2

# === ЛИМИТЫ И ВАЛИДАЦИЯ ===
MAX_USER_INPUT_LENGTH = 2000
MIN_TELEGRAM_ID_LENGTH = 8
MAX_SLOTS_TO_DISPLAY = 20

# === СТАТУСЫ БРОНИРОВАНИЙ ===
BOOKING_STATUS_PENDING = "pending"
BOOKING_STATUS_CONFIRMED = "confirmed"
BOOKING_STATUS_DECLINED = "declined"

# === ЛОКАЦИИ ===
DEFAULT_LOCATIONS = [
    {"name": "Баня", "is_open": True},
    {"name": "Спасалка", "is_open": True},
    {"name": "Глэмпинг", "is_open": False}
]

# === СООБЩЕНИЯ СТАТУСОВ ===
STATUS_ICONS = {
    BOOKING_STATUS_PENDING: "🕐",
    BOOKING_STATUS_CONFIRMED: "✅",
    BOOKING_STATUS_DECLINED: "❌"
}

STATUS_TEXTS = {
    BOOKING_STATUS_PENDING: "Ожидает подтверждения",
    BOOKING_STATUS_CONFIRMED: "Подтверждена",
    BOOKING_STATUS_DECLINED: "Отклонена"
}

# === НАСТРОЙКИ GPT ===
GPT_MODEL = "gpt-4"
GPT_TEMPERATURE = 0.1
GPT_MAX_TOKENS = 1000

# === ФАЙЛЫ И ПУТИ ===
DATABASE_FILE = "data/database.json"
BACKUP_SUFFIX = "_backup"
LOG_FILE = "bot.log"