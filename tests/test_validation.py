"""
Тесты для модуля валидации
"""
import unittest
from bot.utils.validation import (
    validate_telegram_id, 
    sanitize_user_input,
    validate_telegram_handle,
    validate_time_format,
    validate_date_format,
    extract_telegram_handle
)


class TestValidation(unittest.TestCase):
    """Тесты функций валидации."""
    
    def test_validate_telegram_id(self):
        """Тест валидации telegram ID."""
        # Корректные ID
        self.assertTrue(validate_telegram_id("12345678"))
        self.assertTrue(validate_telegram_id("123456789"))
        self.assertTrue(validate_telegram_id("78273571"))
        
        # Некорректные ID
        self.assertFalse(validate_telegram_id("1234567"))  # Слишком короткий
        self.assertFalse(validate_telegram_id("abc123"))   # Не только цифры
        self.assertFalse(validate_telegram_id(""))         # Пустой
        self.assertFalse(validate_telegram_id(None))       # None
        self.assertFalse(validate_telegram_id(123))        # Не строка
    
    def test_sanitize_user_input(self):
        """Тест очистки пользовательского ввода."""
        # Обычный текст
        result = sanitize_user_input("  Привет мир  ")
        self.assertEqual(result, "Привет мир")
        
        # Удаление опасных символов
        result = sanitize_user_input("Текст с <script> и 'кавычками'")
        self.assertEqual(result, "Текст с script и кавычками")
        
        # Ограничение длины (используем короткий текст для теста)
        long_text = "a" * 3000
        result = sanitize_user_input(long_text)
        self.assertLessEqual(len(result), 2000)
        
        # Пустой ввод
        self.assertEqual(sanitize_user_input(""), "")
        self.assertEqual(sanitize_user_input(None), "")
    
    def test_validate_telegram_handle(self):
        """Тест валидации telegram handle."""
        # Корректные handles
        self.assertTrue(validate_telegram_handle("@username"))
        self.assertTrue(validate_telegram_handle("@test_user123"))
        self.assertTrue(validate_telegram_handle("@ivanslyozkin"))
        
        # Некорректные handles
        self.assertFalse(validate_telegram_handle("username"))    # Без @
        self.assertFalse(validate_telegram_handle("@usr"))        # Слишком короткий
        self.assertFalse(validate_telegram_handle("@user-name"))  # Недопустимый символ
        self.assertFalse(validate_telegram_handle(""))           # Пустой
        self.assertFalse(validate_telegram_handle(None))         # None
    
    def test_validate_time_format(self):
        """Тест валидации формата времени."""
        # Корректное время
        self.assertTrue(validate_time_format("14:30"))
        self.assertTrue(validate_time_format("00:00"))
        self.assertTrue(validate_time_format("23:59"))
        self.assertTrue(validate_time_format("9:15"))
        
        # Некорректное время
        self.assertFalse(validate_time_format("25:00"))  # Неверный час
        self.assertFalse(validate_time_format("14:60"))  # Неверные минуты
        self.assertFalse(validate_time_format("1430"))   # Без двоеточия
        self.assertFalse(validate_time_format(""))       # Пустое
        self.assertFalse(validate_time_format(None))     # None
    
    def test_validate_date_format(self):
        """Тест валидации формата даты."""
        # Корректные даты
        self.assertTrue(validate_date_format("2025-07-31"))
        self.assertTrue(validate_date_format("2025-12-31"))
        self.assertTrue(validate_date_format("2025-01-01"))
        
        # Некорректные даты
        self.assertFalse(validate_date_format("25-07-31"))    # Неверный год
        self.assertFalse(validate_date_format("2025/07/31"))  # Неверный разделитель
        self.assertFalse(validate_date_format("31-07-2025"))  # Неверный порядок
        self.assertFalse(validate_date_format(""))           # Пустое
        self.assertFalse(validate_date_format(None))         # None
    
    def test_extract_telegram_handle(self):
        """Тест извлечения telegram handle из текста."""
        # Успешное извлечение
        text1 = "Меня зовут Иван, мой телеграм @ivanslyozkin"
        self.assertEqual(extract_telegram_handle(text1), "@ivanslyozkin")
        
        text2 = "Пишите @test_user для связи"
        self.assertEqual(extract_telegram_handle(text2), "@test_user")
        
        # Не найдено
        text3 = "Обычный текст без handles"
        self.assertIsNone(extract_telegram_handle(text3))
        
        # Пустой ввод
        self.assertIsNone(extract_telegram_handle(""))
        self.assertIsNone(extract_telegram_handle(None))


if __name__ == '__main__':
    unittest.main()