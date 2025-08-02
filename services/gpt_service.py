"""
Улучшенный GPT сервис с полной типизацией и документацией
"""
import openai
import os
import re
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging

from bot.constants import GPT_MODEL, GPT_TEMPERATURE, GPT_MAX_TOKENS
from bot.utils.validation import sanitize_user_input

logger = logging.getLogger(__name__)


class GPTService:
    """Сервис для работы с OpenAI GPT API."""
    
    def __init__(self):
        """
        Инициализация GPT сервиса.
        
        Raises:
            ValueError: Если OPENAI_API_KEY не установлен
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не установлен в переменных окружения")
        
        self.client = openai.OpenAI(api_key=api_key)
        
    async def _retry_gpt_call(self, func, *args, max_retries: int = 3, **kwargs) -> Any:
        """
        Retry wrapper для GPT API calls с exponential backoff.
        
        Args:
            func: Функция для вызова
            max_retries: Максимальное количество попыток
            *args, **kwargs: Аргументы для функции
            
        Returns:
            Результат вызова функции
            
        Raises:
            Exception: Если все попытки исчерпаны
        """
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)  # Синхронный вызов для совместимости
            except openai.RateLimitError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Rate limit exceeded, all retries exhausted: {e}")
                    raise
                wait_time = 2 ** attempt
                logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1})")
                await asyncio.sleep(wait_time)
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                if attempt == max_retries - 1:
                    logger.error(f"API connection error, all retries exhausted: {e}")
                    raise
                wait_time = 2 ** attempt
                logger.warning(f"API connection error, retrying in {wait_time}s (attempt {attempt + 1})")
                await asyncio.sleep(wait_time)
            except openai.APIError as e:
                logger.error(f"OpenAI API error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in GPT call: {e}")
                raise
    
    def analyze_master_profile(self, profile_text: str) -> Dict:
        """
        Анализирует анкету мастера и извлекает структурированную информацию.
        
        Args:
            profile_text: Текст анкеты мастера
            
        Returns:
            Dict с извлеченной информацией: имя, услуги, слоты, локации
        """
        
        prompt = f"""
Проанализируй анкету мастера и извлеки из неё структурированную информацию в формате JSON.

Анкета мастера:
"{profile_text}"

Мне нужно извлечь:
1. Имя мастера (если указано)
2. Список услуг (массаж, рейки, и т.д.)
3. Временные слоты с указанием даты, времени начала и окончания

ВАЖНО: Если в анкете НЕ указана конкретная локация, используй "Баня" по умолчанию для всех слотов.

Правила для временных слотов:
- Если указано "завтра" - используй завтрашнюю дату
- Если указано "вторник 29" - это 29 июля 2025
- Если указано "среда" без даты - это ближайшая среда
- Время всегда в формате HH:MM
- Если сказано "на час" или "на 90 минут", рассчитай время окончания

Формат ответа (строго JSON):
{{
  "name": "имя или null",
  "services": ["список услуг"],
  "time_slots": [
    {{
      "date": "YYYY-MM-DD",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "location": "Баня (или другая если указана)"
    }}
  ],
  "locations": ["Баня"]
}}

Верни только JSON, без дополнительных комментариев.
"""
        
        try:
            # Функция для retry
            def make_request():
                return self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Ты помощник для извлечения структурированной информации из текста. Отвечай только в формате JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    timeout=30.0
                )
            
            # Используем простой retry для совместимости
            max_retries = 3
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    response = make_request()
                    break
                except openai.RateLimitError as e:
                    last_error = e
                    if attempt == max_retries - 1:
                        raise
                    import time
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1})")
                    time.sleep(wait_time)
                except (openai.APIConnectionError, openai.APITimeoutError) as e:
                    last_error = e
                    if attempt == max_retries - 1:
                        raise
                    import time
                    wait_time = 2 ** attempt
                    logger.warning(f"API connection error, retrying in {wait_time}s (attempt {attempt + 1})")
                    time.sleep(wait_time)
                except Exception as e:
                    logger.error(f"OpenAI API error: {e}")
                    raise
            
            result_text = response.choices[0].message.content.strip()
            
            # Попытка извлечь JSON из ответа
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # Если не удалось распарсить, попробуем найти JSON в тексте
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError("GPT не вернул валидный JSON")
            
            logger.info(f"GPT успешно проанализировал анкету: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при анализе анкеты с GPT: {e}")
            # Возвращаем базовую структуру в случае ошибки
            return {
                "name": None,
                "services": ["массаж"],
                "time_slots": [],
                "locations": ["баня"]
            }
    
    def create_fantasy_description(self, original_text: str, extracted_data: Dict) -> str:
        """
        Создает фэнтези-описание мастера в стиле мудрого Осьминога.
        
        Args:
            original_text: Оригинальный текст анкеты
            extracted_data: Извлеченные данные
            
        Returns:
            Фэнтези-описание
        """
        
        name = extracted_data.get("name", "Таинственный мастер")
        services = ", ".join(extracted_data.get("services", ["целительные практики"]))
        locations = ", ".join(extracted_data.get("locations", ["заповедных местах"]))
        
        prompt = f"""
Перепиши описание мастера в стиле мудрого Осьминога - хранителя заповедника. 

Оригинальное описание:
"{original_text}"

Извлеченные данные:
- Имя: {name}
- Услуги: {services}
- Локации: {locations}

Создай атмосферное описание длиной 2-3 предложения, которое:
1. СТРОГО СООТВЕТСТВУЕТ реальным практикам и опыту из оригинального текста
2. Сохраняет ВСЕ важные факты о мастере (опыт, обучение, специальности)
3. Использует стиль заповедника, но БЕЗ ПРИДУМЫВАНИЯ новых фактов
4. Звучит тепло и загадочно, но остается ФАКТИЧЕСКИ ТОЧНЫМ

ПРАВИЛА:
- НЕ добавляй информацию, которой нет в оригинале
- НЕ изменяй реальные факты об обучении или опыте
- СОХРАНЯЙ все упомянутые техники и подходы
- Можешь только добавить атмосферу заповедника к РЕАЛЬНЫМ фактам

Примеры ПРАВИЛЬНОГО стиля:
- "В глубинах заповедника мастер {name}, изучивший [реальную технику], помогает..."
- "Пройдя обучение [где реально учился], теперь в тёплых водах бани..."

Пиши от третьего лица, БЕЗ выдумок.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты мудрый Осьминог, хранитель заповедника. Говори загадочно, но тепло и по существу."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Снижена для точности
                max_tokens=250
            )
            
            result = response.choices[0].message.content.strip()
            logger.info(f"GPT создал фэнтези-описание: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при создании фэнтези-описания: {e}")
            # Возвращаем базовое описание в случае ошибки
            return f"В тёплых глубинах заповедника {name} делится древними знаниями {services}. Его мудрые руки находят путь к исцелению в {locations}."
    
    def parse_time_slots(self, slots_text: str) -> List[Dict]:
        """
        Парсит текст с описанием временных слотов и возвращает структурированные данные.
        
        Args:
            slots_text: Текст с описанием слотов (например: "завтра с 14 до 18 в бане, каждый слот по 1 часу с перерывом по 10 минут между слотами")
            
        Returns:
            Список слотов в формате [{"date": "2025-08-02", "start_time": "14:00", "end_time": "15:00", "location": "баня"}]
        """
        
        prompt = f"""
Проанализируй текст с описанием временных слотов для массажиста и верни ТОЛЬКО JSON массив.

Текст: "{slots_text}"

Правила:
1. Сегодня: 1 августа 2025 года, четверг
2. "Завтра" = 2 августа 2025 (пятница)
3. "Послезавтра" = 3 августа 2025 (суббота)  
4. "В понедельник" = ближайший понедельник (4 августа 2025)
5. "В субботу" = ближайшая суббота (2 августа 2025, если еще не прошла, иначе следующая)

Формат ответа - массив JSON объектов:
[
  {{
    "date": "2025-08-02",
    "start_time": "14:00", 
    "end_time": "15:00",
    "location": "Баня",
    "duration_minutes": 60
  }}
]

Если указан диапазон (например "с 14 до 18") и продолжительность слотов (например "по часу"), создай отдельные слоты.
Если указан перерыв между слотами, учти его.

ВАЖНО: Если локация НЕ указана явно, используй "Баня" для всех слотов.

Верни ТОЛЬКО JSON массив, без дополнительного текста.
"""

        try:
            logger.info(f"Начинаю парсинг слотов: {slots_text}")
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Очищаем ответ от markdown форматирования если есть
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            # Парсим JSON
            slots = json.loads(response_text)
            
            # Валидация структуры
            valid_slots = []
            for slot in slots:
                if all(key in slot for key in ["date", "start_time", "end_time", "location"]):
                    valid_slots.append(slot)
                    
            logger.info(f"Распознано {len(valid_slots)} слотов из текста: {slots_text}")
            return valid_slots
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге слотов с GPT: {e}")
            return []

    def process_master_profile(self, profile_text: str) -> Tuple[Dict, str]:
        """
        Полная обработка анкеты мастера: анализ + создание фэнтези-описания.
        
        Args:
            profile_text: Оригинальный текст анкеты
            
        Returns:
            Tuple (extracted_data, fantasy_description)
        """
        
        logger.info("Начинаю обработку анкеты мастера...")
        
        # Сначала анализируем и извлекаем структурированные данные
        extracted_data = self.analyze_master_profile(profile_text)
        
        # Затем создаем фэнтези-описание
        fantasy_description = self.create_fantasy_description(profile_text, extracted_data)
        
        logger.info("Обработка анкеты завершена успешно")
        return extracted_data, fantasy_description
    
    def generate_personalized_reminder(self, is_master: bool, master_name: str, client_name: str, 
                                     slot_time: str, slot_location: str, reminder_type: str) -> str:
        """
        Генерирует персональное напоминание в стиле Мятного Заповедника.
        
        Args:
            is_master: Напоминание для мастера (True) или клиента (False)
            master_name: Имя мастера
            client_name: Имя клиента  
            slot_time: Время сеанса (например "14:00-15:00")
            slot_location: Локация сеанса
            reminder_type: Тип напоминания ("1_hour" или "15_min")
            
        Returns:
            Персональное напоминание
        """
        
        # Определяем временной контекст
        time_context = "через час" if reminder_type == "1_hour" else "через 15 минут"
        urgency = "готовься" if reminder_type == "1_hour" else "пора!"
        
        # Различные промпты для мастера и клиента
        if is_master:
            role_context = f"Ты напоминаешь мастеру {master_name} о предстоящем сеансе с клиентом {client_name}"
            role_details = "Мастер должен подготовиться: взять необходимые инструменты, проверить локацию, настроиться на работу"
        else:
            role_context = f"Ты напоминаешь клиенту {client_name} о предстоящем массаже у мастера {master_name}"
            role_details = "Клиент должен прийти вовремя, возможно захватить полотенце, расслабиться и настроиться на сеанс"
        
        prompt = f"""
Ты - дух Мятного Заповедника, волшебного места исцеления и гармонии. 🐙🌊

ЗАДАЧА: Создать персональное напоминание о массаже {time_context}.

КОНТЕКСТ:
• {role_context}
• Время сеанса: {slot_time}  
• Локация: {slot_location}
• Степень срочности: {urgency}
• {role_details}

СТИЛЬ НАПИСАНИЯ:
• Мистический, но тёплый и дружелюбный
• Используй образы воды, глубин, исцеления, природы
• Добавляй эмодзи океана/мистики: 🐙🌊💫✨🌿
• Тон веселый, но заботливый
• 2-3 предложения максимум
• Обязательно упомяни время, место и имена

ПРИМЕРЫ МИСТИЧЕСКИХ ФРАЗ:
• "Глубины заповедника нашептывают..."
• "Течения времени несут весть..."  
• "Мятные волны напоминают..."
• "Духи заповедника шепчут..."
• "Исцеляющие воды зовут..."

Создай ПЕРСОНАЛЬНОЕ напоминание прямо сейчас:
"""

        try:
            logger.info(f"Генерирую персональное напоминание {reminder_type} для {'мастера' if is_master else 'клиента'}")
            
            response = self.client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {"role": "system", "content": "Ты - мистический дух Мятного Заповедника, создающий персональные напоминания о массажах."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            reminder = response.choices[0].message.content.strip()
            logger.info("Персональное напоминание сгенерировано успешно")
            return reminder
            
        except Exception as e:
            logger.error(f"Ошибка генерации персонального напоминания: {e}")
            
            # Fallback текст
            if is_master:
                return f"🐙 {master_name}, через {time_context.replace('через ', '')} твой сеанс с {client_name} в {slot_location} ({slot_time}). Глубины заповедника ждут твоего мастерства! ✨"
            else:
                return f"🌊 {client_name}, через {time_context.replace('через ', '')} твой массаж у {master_name} в {slot_location} ({slot_time}). Исцеляющие воды зовут тебя! 💫"