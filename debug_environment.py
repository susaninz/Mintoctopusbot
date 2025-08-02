#!/usr/bin/env python3
"""
Debug скрипт для проверки environment variables в production
"""
import os
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_environment():
    """Проверяет все возможные варианты environment variables для OpenAI API"""
    
    print("🔍 ДИАГНОСТИКА ENVIRONMENT VARIABLES")
    print("=" * 60)
    print()
    
    # Загружаем .env если есть
    print("📄 Загружаем .env файл...")
    try:
        load_dotenv()
        print("✅ load_dotenv() выполнен")
    except Exception as e:
        print(f"❌ Ошибка load_dotenv(): {e}")
    
    print()
    print("🔑 ПРОВЕРКА OPENAI API КЛЮЧЕЙ:")
    
    # Все возможные варианты названий
    openai_variants = [
        "OPENAI_API_KEY",
        "OPENAI_KEY", 
        "OpenAI_API_Key",
        "OPEN_AI_API_KEY",
        "openai_api_key",
        "OPENAI_SECRET_KEY",
        "GPT_API_KEY",
        "OPENAI_TOKEN"
    ]
    
    found_keys = []
    
    for variant in openai_variants:
        value = os.getenv(variant)
        if value:
            # Маскируем ключ для безопасности
            if len(value) > 8:
                masked = value[:4] + "..." + value[-4:]
            else:
                masked = "***"
            print(f"✅ {variant}: {masked}")
            found_keys.append((variant, value))
        else:
            print(f"❌ {variant}: НЕ НАЙДЕН")
    
    print()
    print("🔑 НАЙДЕННЫЕ КЛЮЧИ:")
    if found_keys:
        for variant, value in found_keys:
            print(f"   {variant} = {value[:4]}...{value[-4:]}")
    else:
        print("   ❌ НИ ОДНОГО КЛЮЧА НЕ НАЙДЕНО")
    
    print()
    print("🌐 ВСЕ ENVIRONMENT VARIABLES:")
    
    # Показываем все env vars с фильтром по ключевым словам
    relevant_vars = []
    for key, value in os.environ.items():
        key_lower = key.lower()
        if any(keyword in key_lower for keyword in ['openai', 'gpt', 'api', 'key', 'token', 'secret']):
            if len(value) > 8:
                masked = value[:4] + "..." + value[-4:]
            else:
                masked = "***"
            relevant_vars.append((key, masked))
    
    if relevant_vars:
        for key, masked_value in relevant_vars:
            print(f"   {key}: {masked_value}")
    else:
        print("   ❌ Нет переменных с API/ключевыми словами")
    
    print()
    print("🧪 ТЕСТ GPT SERVICE:")
    
    try:
        from services.gpt_service import GPTService
        gpt = GPTService()
        print(f"✅ GPTService создан, fallback_mode: {gpt.fallback_mode}")
        
        if not gpt.fallback_mode:
            print("🎉 GPT API ДОСТУПЕН!")
            # Тестируем простой запрос
            try:
                test_result = gpt.parse_time_slots("завтра в 14")
                print(f"✅ Тест парсинга успешен: {test_result}")
            except Exception as e:
                print(f"❌ Ошибка тестирования GPT: {e}")
        else:
            print("⚠️ GPT работает в fallback режиме")
            
    except Exception as e:
        print(f"❌ Ошибка создания GPTService: {e}")
    
    print()
    print("📋 РЕКОМЕНДАЦИИ:")
    
    if found_keys:
        print("✅ API ключи найдены, GPT должен работать")
        print("   Проверьте правильность ключа и доступ к OpenAI API")
    else:
        print("❌ API ключи НЕ найдены в environment")
        print("   Проверьте настройки Railway.app environment variables")
        print("   Убедитесь что переменная называется именно OPENAI_API_KEY")
    
    return found_keys

if __name__ == "__main__":
    debug_environment()