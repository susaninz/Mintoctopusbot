#!/usr/bin/env python3
"""
EMERGENCY DATA RESTORATION SCRIPT
Копирует данные из локальных файлов в volume
"""

import json
import os
import shutil
from datetime import datetime

def restore_data():
    print(f"🚨 {datetime.now()}: EMERGENCY DATA RESTORATION")
    
    # Проверяем что volume пустой
    volume_path = "/app/data"
    if os.path.exists(volume_path):
        print(f"📁 Volume exists: {volume_path}")
        files = os.listdir(volume_path)
        print(f"📂 Files in volume: {files}")
    else:
        print(f"❌ Volume path not found: {volume_path}")
        return
    
    # Локальные данные для восстановления
    local_data = {
        "database.json": "data/database.json",
        "bug_reports.json": "data/bug_reports.json", 
        "database_backup.json": "data/database_backup.json",
        "database_backup_before_import.json": "data/database_backup_before_import.json"
    }
    
    print("📋 Список файлов для восстановления:")
    for target, source in local_data.items():
        if os.path.exists(source):
            size = os.path.getsize(source)
            print(f"  ✅ {source} -> {volume_path}/{target} ({size} bytes)")
        else:
            print(f"  ❌ {source} NOT FOUND")
    
    # Копируем файлы
    for target, source in local_data.items():
        if os.path.exists(source):
            target_path = os.path.join(volume_path, target)
            try:
                shutil.copy2(source, target_path)
                print(f"  ✅ Copied: {source} -> {target_path}")
            except Exception as e:
                print(f"  ❌ Error copying {source}: {e}")
    
    # Копируем папку backups
    backups_source = "data/backups"
    backups_target = os.path.join(volume_path, "backups")
    
    if os.path.exists(backups_source):
        try:
            if os.path.exists(backups_target):
                shutil.rmtree(backups_target)
            shutil.copytree(backups_source, backups_target)
            print(f"✅ Copied backups: {backups_source} -> {backups_target}")
        except Exception as e:
            print(f"❌ Error copying backups: {e}")
    
    print("🔍 Final volume contents:")
    if os.path.exists(volume_path):
        for root, dirs, files in os.walk(volume_path):
            level = root.replace(volume_path, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                print(f"{subindent}{file} ({size} bytes)")

if __name__ == "__main__":
    restore_data()