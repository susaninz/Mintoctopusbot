"""
Тесты для сервиса данных
"""
import unittest
import tempfile
import os
import json
from bot.services.data_service import DataService


class TestDataService(unittest.TestCase):
    """Тесты для DataService."""
    
    def setUp(self):
        """Настройка для каждого теста."""
        # Создаем временный файл для тестов
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        
        self.data_service = DataService(self.temp_file.name)
    
    def tearDown(self):
        """Очистка после каждого теста."""
        # Удаляем временный файл
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_create_empty_structure(self):
        """Тест создания пустой структуры данных."""
        data = self.data_service.load_data()
        
        self.assertIn("masters", data)
        self.assertIn("bookings", data)
        self.assertIn("locations", data)
        self.assertIn("settings", data)
        
        self.assertEqual(data["masters"], [])
        self.assertEqual(data["bookings"], [])
        self.assertIsInstance(data["locations"], list)
        self.assertIsInstance(data["settings"], dict)
    
    def test_save_and_load_data(self):
        """Тест сохранения и загрузки данных."""
        test_data = {
            "masters": [{"name": "Test Master", "telegram_id": "12345678"}],
            "bookings": [],
            "locations": [],
            "settings": {}
        }
        
        # Сохраняем данные
        result = self.data_service.save_data(test_data)
        self.assertTrue(result)
        
        # Загружаем данные
        loaded_data = self.data_service.load_data()
        self.assertEqual(loaded_data["masters"][0]["name"], "Test Master")
        self.assertEqual(loaded_data["masters"][0]["telegram_id"], "12345678")
    
    def test_find_master_by_id(self):
        """Тест поиска мастера по ID."""
        # Сначала добавляем тестового мастера
        test_data = {
            "masters": [
                {"name": "Master 1", "telegram_id": "12345678"},
                {"name": "Master 2", "telegram_id": "87654321"}
            ],
            "bookings": [],
            "locations": [],
            "settings": {}
        }
        self.data_service.save_data(test_data)
        
        # Ищем существующего мастера
        master = self.data_service.find_master_by_id("12345678")
        self.assertIsNotNone(master)
        self.assertEqual(master["name"], "Master 1")
        
        # Ищем несуществующего мастера
        master = self.data_service.find_master_by_id("99999999")
        self.assertIsNone(master)
        
        # Некорректный ID
        master = self.data_service.find_master_by_id("invalid")
        self.assertIsNone(master)
    
    def test_find_master_by_handle(self):
        """Тест поиска мастера по handle."""
        test_data = {
            "masters": [
                {"name": "Master 1", "telegram_id": "12345678", "telegram_handle": "@master1"},
                {"name": "Master 2", "telegram_id": "87654321", "telegram_handle": "@master2"}
            ],
            "bookings": [],
            "locations": [],
            "settings": {}
        }
        self.data_service.save_data(test_data)
        
        # Ищем существующего мастера
        master = self.data_service.find_master_by_handle("@master1")
        self.assertIsNotNone(master)
        self.assertEqual(master["name"], "Master 1")
        
        # Ищем несуществующего мастера
        master = self.data_service.find_master_by_handle("@nonexistent")
        self.assertIsNone(master)
    
    def test_add_master(self):
        """Тест добавления мастера."""
        master_data = {
            "name": "New Master",
            "telegram_id": "12345678",
            "telegram_handle": "@newmaster"
        }
        
        # Добавляем мастера
        result = self.data_service.add_master(master_data)
        self.assertTrue(result)
        
        # Проверяем, что мастер добавлен
        master = self.data_service.find_master_by_id("12345678")
        self.assertIsNotNone(master)
        self.assertEqual(master["name"], "New Master")
        self.assertIn("created_at", master)
        self.assertTrue(master["is_active"])
        
        # Попытка добавить дубликат
        result = self.data_service.add_master(master_data)
        self.assertFalse(result)
    
    def test_link_telegram_id(self):
        """Тест привязки telegram ID."""
        test_data = {
            "masters": [
                {"name": "Master 1", "telegram_id": "fake123", "telegram_handle": "@master1"}
            ],
            "bookings": [],
            "locations": [],
            "settings": {}
        }
        self.data_service.save_data(test_data)
        
        # Привязываем настоящий ID
        result = self.data_service.link_telegram_id("@master1", "87654321")
        self.assertTrue(result)
        
        # Проверяем обновление
        master = self.data_service.find_master_by_id("87654321")
        self.assertIsNotNone(master)
        self.assertEqual(master["name"], "Master 1")
        self.assertIn("verified_at", master)
        
        # Попытка привязать к несуществующему handle
        result = self.data_service.link_telegram_id("@nonexistent", "11111111")
        self.assertFalse(result)
    
    def test_get_all_masters(self):
        """Тест получения всех активных мастеров."""
        test_data = {
            "masters": [
                {"name": "Active Master", "telegram_id": "12345678", "is_active": True},
                {"name": "Inactive Master", "telegram_id": "87654321", "is_active": False},
                {"name": "Default Master", "telegram_id": "11111111"}  # is_active по умолчанию True
            ],
            "bookings": [],
            "locations": [],
            "settings": {}
        }
        self.data_service.save_data(test_data)
        
        masters = self.data_service.get_all_masters()
        self.assertEqual(len(masters), 2)  # Только активные
        
        master_names = [master["name"] for master in masters]
        self.assertIn("Active Master", master_names)
        self.assertIn("Default Master", master_names)
        self.assertNotIn("Inactive Master", master_names)


if __name__ == '__main__':
    unittest.main()