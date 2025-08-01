import logging
import os
import json
from typing import Dict

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from services.gpt_service import GPTService

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настраиваем логирование, чтобы видеть информацию о работе бота
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Константы для кнопок ---
MASTER_ROLE = "Я мну 🐙"
CLIENT_ROLE = "Хочу, чтобы меня помяли 🙏"

# Кнопки для мастеров
MY_SLOTS = "Мои слоты 📋"
ADD_SLOTS = "Добавить слоты ➕"
MY_PROFILE = "Мой профиль 👤"

# Кнопки для гостей  
VIEW_MASTERS = "Посмотреть мастеров 👥"
MY_BOOKINGS = "Мои записи 📅"

# Общие кнопки
BACK_TO_MENU = "Главное меню 🏠"
CHANGE_ROLE = "Сменить роль 🔄"

# --- Состояния для разговора ---
# (убраны, так как теперь используем простые состояния в user_states)

# --- Глобальные объекты ---
gpt_service = GPTService()

# --- Хранилище состояний пользователей ---
user_states: Dict[str, Dict] = {}

# --- Простые функции для работы с данными ---
def load_data():
    """Загружает данные из JSON файла."""
    try:
        if os.path.exists("data/database.json"):
            with open("data/database.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {"masters": {}, "users": {}}

def save_data(data):
    """Сохраняет данные в JSON файл."""
    os.makedirs("data", exist_ok=True)
    with open("data/database.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_state(user_id: str) -> Dict:
    """Получает состояние пользователя или создает новое."""
    if user_id not in user_states:
        user_states[user_id] = {"role": None, "awaiting": None}
    return user_states[user_id]


def get_master_menu_keyboard():
    """Возвращает клавиатуру для мастера."""
    return ReplyKeyboardMarkup([
        [MY_SLOTS, ADD_SLOTS],
        [MY_PROFILE, CHANGE_ROLE],
        [BACK_TO_MENU]
    ], resize_keyboard=True)


def get_client_menu_keyboard():
    """Возвращает клавиатуру для клиента."""
    return ReplyKeyboardMarkup([
        [VIEW_MASTERS],
        [MY_BOOKINGS, CHANGE_ROLE],
        [BACK_TO_MENU]
    ], resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение с кнопками выбора роли."""
    reply_keyboard = [[MASTER_ROLE, CLIENT_ROLE]]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        f"Привет, {update.effective_user.mention_html()}! Я мудрый Осьминог, хранитель этого места.\n\n"
        "Чтобы начать, выбери, кто ты:",
        reply_markup=markup,
        parse_mode='HTML'
    )
    
    # Сбрасываем состояние пользователя
    user_id = str(update.effective_user.id)
    user_states[user_id] = {"role": None, "awaiting": None}


async def handle_role_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выбор роли пользователя."""
    user_choice = update.message.text
    user_id = str(update.effective_user.id)
    user_state = get_user_state(user_id)
    
    if user_choice == MASTER_ROLE:
        user_state["role"] = "master"
        
        # Проверяем, не зарегистрирован ли уже этот мастер
        data = load_data()
        existing_master = data.get("masters", {}).get(user_id)
        if existing_master:
            await update.message.reply_text(
                f"О, {existing_master['name']}! Добро пожаловать обратно в заповедник! 🌊\n\n"
                f"Выбери, что хочешь сделать:",
                reply_markup=get_master_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                "Великолепно! Расскажи о себе в одном сообщении: как тебя зовут, какой у тебя опыт, "
                "какие практики предлагаешь и в какое время и где ты свободен? "
                "Я всё пойму и оформлю в лучшем виде.",
                reply_markup=ReplyKeyboardRemove()
            )
            user_state["awaiting"] = "master_profile"
        
    elif user_choice == CLIENT_ROLE:
        user_state["role"] = "client"
        
        await update.message.reply_text(
            "Чудесно! Добро пожаловать в заповедник исцеления! 🌿\n\n"
            "Выбери, что хочешь сделать:",
            reply_markup=get_client_menu_keyboard()
        )
    else:
        await update.message.reply_text("Кажется, я не совсем понял. Пожалуйста, используй кнопки.")


async def process_master_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает анкету мастера через GPT."""
    user_id = str(update.effective_user.id)
    profile_text = update.message.text
    
    await update.message.reply_text(
        "Хм... позволь мне вглядеться в глубины твоих слов... 🐙\n"
        "Это может занять несколько мгновений..."
    )
    
    try:
        # Обрабатываем анкету через GPT
        extracted_data, fantasy_description = gpt_service.process_master_profile(profile_text)
        
        # Определяем имя мастера
        master_name = extracted_data.get("name") or update.effective_user.first_name or "Безымянный мастер"
        
        # Сохраняем мастера в базе данных
        data = load_data()
        data.setdefault("masters", {})[user_id] = {
            "name": master_name,
            "original_description": profile_text,
            "fantasy_description": fantasy_description,
            "services": extracted_data.get("services", []),
            "time_slots": extracted_data.get("time_slots", []),
            "is_active": True,
            "bookings": []
        }
        save_data(data)
        success = True
        
        if success:
            # Показываем результат мастеру
            response_text = (
                f"🌊 Глубины раскрыли мне твою суть, {master_name}!\n\n"
                f"**Твоё описание в заповеднике:**\n{fantasy_description}\n\n"
                f"**Извлеченные услуги:** {', '.join(extracted_data.get('services', []))}\n"
                f"**Временные слоты:** {len(extracted_data.get('time_slots', []))} добавлено\n\n"
                "Теперь гости смогут найти тебя! Выбери, что делать дальше:"
            )
            
            await update.message.reply_text(
                response_text, 
                parse_mode='Markdown',
                reply_markup=get_master_menu_keyboard()
            )
            logger.info(f"Успешно зарегистрирован мастер {master_name} (ID: {user_id})")
            
        else:
            await update.message.reply_text(
                "Кажется, ты уже состоишь в рядах наших мастеров. "
                "Если хочешь обновить информацию, сначала свяжись с администратором.",
                reply_markup=get_master_menu_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обработке анкеты мастера: {e}")
        await update.message.reply_text(
            "Ой! Что-то пошло не так в глубинах моего разума... 😔\n"
            "Попробуй ещё раз, или обратись к администратору.",
            reply_markup=get_master_menu_keyboard()
        )
    
    # Сбрасываем состояние ожидания
    user_state = get_user_state(user_id)
    user_state["awaiting"] = None


async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия на кнопки меню."""
    user_choice = update.message.text
    user_id = str(update.effective_user.id)
    user_state = get_user_state(user_id)
    
    if user_choice == MY_SLOTS:
        await show_my_slots(update, context)
    elif user_choice == ADD_SLOTS:
        await handle_add_slots_request(update, context)
    elif user_choice == MY_PROFILE:
        await show_my_profile(update, context)
    elif user_choice == VIEW_MASTERS:
        await show_masters_list(update, context)
    elif user_choice == MY_BOOKINGS:
        await show_my_bookings(update, context)
    elif user_choice == CHANGE_ROLE:
        await start(update, context)
    elif user_choice == BACK_TO_MENU:
        if user_state.get("role") == "master":
            await update.message.reply_text(
                "Главное меню мастера:",
                reply_markup=get_master_menu_keyboard()
            )
        elif user_state.get("role") == "client":
            await update.message.reply_text(
                "Главное меню гостя:",
                reply_markup=get_client_menu_keyboard()
            )
        else:
            await start(update, context)
    else:
        await update.message.reply_text(
            "Не понимаю этой команды. Используй кнопки меню."
        )


async def show_my_slots(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает слоты мастера."""
    user_id = str(update.effective_user.id)
    data = load_data()
    master = data.get("masters", {}).get(user_id)
    
    if not master:
        await update.message.reply_text(
            "Кажется, ты ещё не зарегистрирован как мастер.",
            reply_markup=get_master_menu_keyboard()
        )
        return
    
    time_slots = master.get("time_slots", [])
    # Упрощаем - пока показываем все слоты как доступные
    available_slots = time_slots
    
    if not time_slots:
        await update.message.reply_text(
            "У тебя пока нет временных слотов. Добавь их через кнопку 'Добавить слоты'!",
            reply_markup=get_master_menu_keyboard()
        )
        return
    
    response = f"📋 **Твои временные слоты, {master['name']}:**\n\n"
    
    for i, slot in enumerate(time_slots):
        slot_id = f"{user_id}_{i}"
        status = "🟢 Свободен" if any(s.get("slot_id") == slot_id for s in available_slots) else "🔴 Занят"
        
        response += (
            f"**{i+1}.** {slot.get('date', 'Дата не указана')} "
            f"{slot.get('start_time', '??:??')} - {slot.get('end_time', '??:??')}\n"
            f"📍 {slot.get('location', 'Локация не указана')} | {status}\n\n"
        )
    
    response += "Через кнопку 'Добавить слоты' можно добавить новые временные окна."
    
    await update.message.reply_text(
        response,
        parse_mode='Markdown',
        reply_markup=get_master_menu_keyboard()
    )


async def show_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает профиль мастера."""
    user_id = str(update.effective_user.id)
    data = load_data()
    master = data.get("masters", {}).get(user_id)
    
    if not master:
        await update.message.reply_text(
            "Кажется, ты ещё не зарегистрирован как мастер.",
            reply_markup=get_master_menu_keyboard()
        )
        return
    
    response = (
        f"👤 **Твой профиль, {master['name']}:**\n\n"
        f"🎭 **Фэнтези-описание:**\n{master['fantasy_description']}\n\n"
        f"📝 **Твои оригинальные слова:**\n{master['original_description']}\n\n"
        f"🛠 **Услуги:** {', '.join(master.get('services', []))}\n"
        f"⏰ **Слотов создано:** {len(master.get('time_slots', []))}"
    )
    
    await update.message.reply_text(
        response,
        parse_mode='Markdown',
        reply_markup=get_master_menu_keyboard()
    )


async def handle_add_slots_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запрос на добавление новых слотов."""
    await update.message.reply_text(
        "Расскажи, какие новые слоты хочешь добавить? Например:\n\n"
        "• 'Завтра с 14:00 до 16:00 в бане'\n"
        "• 'В субботу в 18:00 на полтора часа в глэмпинге'\n"
        "• 'Воскресенье с 10 до 12 в спасалке'\n\n"
        "Я пойму и добавлю всё в твоё расписание!",
        reply_markup=ReplyKeyboardRemove()
    )
    # TODO: Реализовать добавление новых слотов через GPT


async def show_masters_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список всех мастеров."""
    data = load_data()
    masters = [master for master in data.get("masters", {}).values() if master.get("is_active", True)]
    
    if not masters:
        await update.message.reply_text(
            "Пока в заповеднике нет активных мастеров. Но скоро они появятся, как рассвет над тихими водами...",
            reply_markup=get_client_menu_keyboard()
        )
        return
    
    response = "👥 **Мастера заповедника:**\n\n"
    
    for i, master in enumerate(masters, 1):
        # Упрощаем - показываем количество всех слотов
        available_slots = master.get("time_slots", [])
        response += (
            f"**{i}. {master['name']}**\n"
            f"{master['fantasy_description']}\n"
            f"🛠 {', '.join(master.get('services', []))}\n"
            f"🟢 Слотов доступно: {len(available_slots)}\n\n"
        )
    
    await update.message.reply_text(
        response,
        parse_mode='Markdown',
        reply_markup=get_client_menu_keyboard()
    )


async def show_my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает записи гостя."""
    await update.message.reply_text(
        "📅 Твои записи:\n\nПока у тебя нет записей к мастерам.",
        reply_markup=get_client_menu_keyboard()
    )


async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает все текстовые сообщения и кнопки."""
    user_id = str(update.effective_user.id)
    text = update.message.text
    user_state = get_user_state(user_id)
    
    # Отладочное логирование
    logger.info(f"Получено сообщение от пользователя {user_id}: '{text}'")
    logger.info(f"Состояние пользователя: {user_state}")
    
    # Проверяем, ждем ли мы профиль мастера
    if user_state.get("awaiting") == "master_profile":
        logger.info("Обрабатываем как профиль мастера")
        await process_master_profile(update, context)
        return
    
    # Обрабатываем выбор роли
    if text in [MASTER_ROLE, CLIENT_ROLE]:
        logger.info(f"Обрабатываем выбор роли: {text}")
        await handle_role_choice(update, context)
        return
    
    # Обрабатываем кнопки меню
    logger.info("Обрабатываем как кнопку меню")
    await handle_menu_buttons(update, context)


def main() -> None:
    """Запускает бота."""
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        logger.error("Не найден TELEGRAM_TOKEN. Убедись, что он есть в .env файле.")
        return

    application = Application.builder().token(telegram_token).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))

    logger.info("Осьминог расправляет свои щупальца и выходит в онлайн...")
    application.run_polling()


if __name__ == "__main__":
    main()