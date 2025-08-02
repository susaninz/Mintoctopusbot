#!/usr/bin/env python3
"""
Безопасный деплой с проверками целостности данных
"""

import json
import subprocess
import sys
import os
from datetime import datetime
from services.backup_manager import backup_manager
from services.safe_data_manager import safe_data_manager

def run_command(command, description):
    """Выполняет команду с логированием."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        print(f"✅ {description} - Успешно")
        if result.stdout:
            print(f"   Вывод: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Ошибка")
        print(f"   Код ошибки: {e.returncode}")
        print(f"   Вывод: {e.stdout}")
        print(f"   Ошибки: {e.stderr}")
        return False

def check_data_integrity():
    """Проверяет целостность данных перед деплоем."""
    print("🔍 Проверка целостности данных...")
    
    health_status = safe_data_manager.get_health_status()
    
    if not health_status.get('database_valid', False):
        print("❌ База данных не прошла проверку целостности!")
        return False
    
    if not health_status.get('has_critical_data', False):
        print("⚠️ База данных не содержит критических данных!")
        response = input("Продолжить деплой? (y/N): ")
        if response.lower() != 'y':
            return False
    
    stats = health_status.get('data_stats', {})
    print(f"📊 Статистика данных:")
    print(f"   - Мастеров: {stats.get('masters', 0)}")
    print(f"   - Записей на мастеров: {stats.get('bookings', 0)}")
    print(f"   - Записей на устройства: {stats.get('device_bookings', 0)}")
    print(f"   - Устройств: {stats.get('devices', 0)}")
    print(f"   - Размер файла: {stats.get('file_size', 0)} байт")
    
    return True

def create_deployment_backup():
    """Создает резервную копию перед деплоем."""
    print("📦 Создание резервной копии перед деплоем...")
    
    backup_path = backup_manager.create_pre_deployment_backup()
    if backup_path:
        print(f"✅ Резервная копия создана: {backup_path}")
        return backup_path
    else:
        print("❌ Не удалось создать резервную копию!")
        return None

def cleanup_old_backups():
    """Очищает старые резервные копии."""
    print("🗑️ Очистка старых резервных копий...")
    removed_count = backup_manager.cleanup_old_backups(keep_days=7)
    print(f"✅ Удалено {removed_count} старых резервных копий")

def verify_git_status():
    """Проверяет статус git репозитория."""
    print("🔍 Проверка git статуса...")
    
    # Проверяем, есть ли незакоммиченные изменения
    result = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True)
    if result.stdout.strip():
        print("⚠️ Есть незакоммиченные изменения:")
        print(result.stdout)
        response = input("Продолжить деплой? (y/N): ")
        if response.lower() != 'y':
            return False
    
    # Проверяем, есть ли unpushed коммиты
    result = subprocess.run("git log --oneline origin/main..HEAD", shell=True, capture_output=True, text=True)
    if result.stdout.strip():
        print("⚠️ Есть непушнутые коммиты:")
        print(result.stdout)
        response = input("Запушить коммиты и продолжить? (y/N): ")
        if response.lower() == 'y':
            if not run_command("git push origin main", "Пуш коммитов"):
                return False
        else:
            return False
    
    return True

def test_bot_locally():
    """Быстрый тест бота локально."""
    print("🧪 Быстрый тест бота...")
    
    try:
        # Проверяем, что основной файл бота импортируется без ошибок
        result = subprocess.run(
            "python3 -c 'import working_bot; print(\"Bot imports successfully\")'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ Импорт бота прошел успешно")
            return True
        else:
            print(f"❌ Ошибка импорта бота: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Тест бота превысил время ожидания")
        return False
    except Exception as e:
        print(f"❌ Ошибка тестирования бота: {e}")
        return False

def deploy_to_railway():
    """Деплоит на Railway."""
    print("🚀 Деплой на Railway...")
    return run_command("railway up", "Деплой Railway")

def verify_deployment():
    """Проверяет успешность деплоя."""
    print("🔍 Проверка деплоя...")
    
    # Даем время на запуск
    import time
    print("⏳ Ожидание запуска сервиса (30 секунд)...")
    time.sleep(30)
    
    # Проверяем healthcheck
    healthcheck_result = run_command(
        "curl -s https://mintoctopusbot-production.up.railway.app/health",
        "Проверка healthcheck"
    )
    
    if healthcheck_result:
        print("✅ Деплой успешен - бот отвечает на healthcheck")
        return True
    else:
        print("❌ Деплой неуспешен - бот не отвечает")
        return False

def rollback_deployment(backup_path):
    """Откатывает деплой в случае проблем."""
    print(f"🔄 Откат деплоя...")
    
    print("⚠️ Автоматический откат кода не поддерживается")
    print("📦 Для отката данных используйте резервную копию:")
    print(f"   {backup_path}")
    print("\n🔧 Для отката кода:")
    print("   1. git log --oneline")
    print("   2. git reset --hard <hash_последнего_стабильного_коммита>")
    print("   3. git push --force origin main")

def main():
    """Основная функция безопасного деплоя."""
    print("🛡️ Безопасный деплой Mintoctopus Bot")
    print("=" * 50)
    
    # 1. Проверяем целостность данных
    if not check_data_integrity():
        print("❌ Деплой прерван из-за проблем с данными")
        sys.exit(1)
    
    # 2. Создаем резервную копию
    backup_path = create_deployment_backup()
    if not backup_path:
        print("❌ Деплой прерван - не удалось создать резервную копию")
        sys.exit(1)
    
    # 3. Очищаем старые бэкапы
    cleanup_old_backups()
    
    # 4. Проверяем git статус
    if not verify_git_status():
        print("❌ Деплой прерван из-за проблем с git")
        sys.exit(1)
    
    # 5. Тестируем бота локально
    if not test_bot_locally():
        print("❌ Деплой прерван - бот не прошел локальный тест")
        sys.exit(1)
    
    # 6. Деплоим на Railway
    if not deploy_to_railway():
        print("❌ Деплой неуспешен")
        rollback_deployment(backup_path)
        sys.exit(1)
    
    # 7. Проверяем деплой
    if not verify_deployment():
        print("❌ Деплой не прошел проверку")
        rollback_deployment(backup_path)
        sys.exit(1)
    
    # 8. Финальные проверки
    print("\n🎉 Деплой завершен успешно!")
    
    health_status = safe_data_manager.get_health_status()
    print(f"\n📊 Финальная статистика:")
    print(f"   - Данные валидны: {'✅' if health_status.get('database_valid') else '❌'}")
    print(f"   - Резервных копий: {health_status.get('total_backups', 0)}")
    print(f"   - Последний бэкап: {backup_path}")
    print(f"   - Время деплоя: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()