"""
Bug Tracker - система отслеживания и логирования багов
"""

import json
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class BugStatus(Enum):
    REPORTED = "reported"
    ANALYZING = "analyzing"
    FIXING = "fixing"
    FIXED = "fixed"
    TESTED = "tested"
    CLOSED = "closed"
    REJECTED = "rejected"
    POSTPONED = "postponed"

class BugPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

class BugTracker:
    def __init__(self, bugs_file: str = "data/bug_tracking.json"):
        self.bugs_file = bugs_file
        self.bugs_data = self._load_bugs_data()
        
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(self.bugs_file), exist_ok=True)
    
    def _load_bugs_data(self) -> Dict:
        """Загружает данные о багах из файла"""
        if os.path.exists(self.bugs_file):
            try:
                with open(self.bugs_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"❌ Ошибка загрузки данных багов: {e}")
                return self._create_empty_structure()
        else:
            return self._create_empty_structure()
    
    def _create_empty_structure(self) -> Dict:
        """Создает пустую структуру данных"""
        return {
            "bugs": [],
            "statistics": {
                "total_reported": 0,
                "total_fixed": 0,
                "total_auto_fixed": 0,
                "last_updated": datetime.now().isoformat()
            },
            "settings": {
                "auto_close_after_days": 30,
                "notification_threshold": 5
            }
        }
    
    def _save_bugs_data(self):
        """Сохраняет данные о багах в файл"""
        try:
            # Обновляем статистику перед сохранением
            self._update_statistics()
            
            with open(self.bugs_file, 'w', encoding='utf-8') as f:
                json.dump(self.bugs_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"✅ Данные багов сохранены в {self.bugs_file}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных багов: {e}")
    
    def register_bug(self, bug_report: Dict, bug_analysis: Dict = None) -> str:
        """Регистрирует новый баг в системе отслеживания"""
        try:
            bug_id = bug_report.get('id') or self._generate_bug_id()
            
            bug_entry = {
                "id": bug_id,
                "status": BugStatus.REPORTED.value,
                "priority": self._determine_priority(bug_report, bug_analysis),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "reporter": {
                    "user_id": bug_report.get('user_id'),
                    "username": bug_report.get('username'),
                    "telegram_id": bug_report.get('telegram_id')
                },
                "details": {
                    "description": bug_report.get('description', ''),
                    "bug_type": bug_report.get('bug_type', ''),
                    "steps_to_reproduce": bug_report.get('steps_to_reproduce', ''),
                    "expected_behavior": bug_report.get('expected_behavior', ''),
                    "actual_behavior": bug_report.get('actual_behavior', '')
                },
                "analysis": bug_analysis or {},
                "actions": [],
                "notifications_sent": [],
                "fix_attempts": [],
                "tags": self._generate_tags(bug_report, bug_analysis)
            }
            
            self.bugs_data["bugs"].append(bug_entry)
            self._save_bugs_data()
            
            logger.info(f"📋 Баг {bug_id} зарегистрирован в системе отслеживания")
            return bug_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка регистрации бага: {e}")
            return ""
    
    def update_bug_status(self, bug_id: str, new_status: BugStatus, details: str = "") -> bool:
        """Обновляет статус бага"""
        try:
            bug = self._find_bug_by_id(bug_id)
            if not bug:
                logger.warning(f"⚠️ Баг {bug_id} не найден")
                return False
            
            old_status = bug["status"]
            bug["status"] = new_status.value
            bug["updated_at"] = datetime.now().isoformat()
            
            # Добавляем запись о действии
            action = {
                "timestamp": datetime.now().isoformat(),
                "action": "status_change",
                "from_status": old_status,
                "to_status": new_status.value,
                "details": details,
                "automated": False
            }
            bug["actions"].append(action)
            
            self._save_bugs_data()
            
            logger.info(f"📊 Статус бага {bug_id}: {old_status} → {new_status.value}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса бага {bug_id}: {e}")
            return False
    
    def log_fix_attempt(self, bug_id: str, fix_details: Dict, success: bool = False) -> bool:
        """Логирует попытку исправления бага"""
        try:
            bug = self._find_bug_by_id(bug_id)
            if not bug:
                return False
            
            fix_attempt = {
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "method": fix_details.get('method', 'manual'),  # manual/automatic
                "description": fix_details.get('description', ''),
                "modified_files": fix_details.get('modified_files', []),
                "changes_made": fix_details.get('changes_made', []),
                "tester": fix_details.get('tester', 'system'),
                "test_results": fix_details.get('test_results', '')
            }
            
            bug["fix_attempts"].append(fix_attempt)
            bug["updated_at"] = datetime.now().isoformat()
            
            # Если исправление успешно, обновляем статус
            if success:
                bug["status"] = BugStatus.FIXED.value
                action = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "bug_fixed",
                    "method": fix_attempt["method"],
                    "details": fix_attempt["description"],
                    "automated": fix_attempt["method"] == "automatic"
                }
                bug["actions"].append(action)
            
            self._save_bugs_data()
            
            status_text = "✅ Успешно" if success else "❌ Неудачно"
            logger.info(f"🔧 Попытка исправления {bug_id}: {status_text}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка логирования исправления {bug_id}: {e}")
            return False
    
    def log_notification_sent(self, bug_id: str, notification_type: str, recipient: str) -> bool:
        """Логирует отправленное уведомление"""
        try:
            bug = self._find_bug_by_id(bug_id)
            if not bug:
                return False
            
            notification = {
                "timestamp": datetime.now().isoformat(),
                "type": notification_type,  # critical_alert, daily_digest, fix_notification
                "recipient": recipient,
                "status": "sent"
            }
            
            bug["notifications_sent"].append(notification)
            bug["updated_at"] = datetime.now().isoformat()
            
            self._save_bugs_data()
            
            logger.debug(f"📱 Уведомление {notification_type} отправлено для {bug_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка логирования уведомления {bug_id}: {e}")
            return False
    
    def get_bug_details(self, bug_id: str) -> Optional[Dict]:
        """Возвращает детальную информацию о баге"""
        return self._find_bug_by_id(bug_id)
    
    def get_bugs_by_status(self, status: BugStatus) -> List[Dict]:
        """Возвращает список багов с определенным статусом"""
        return [bug for bug in self.bugs_data["bugs"] if bug["status"] == status.value]
    
    def get_bugs_by_priority(self, priority: BugPriority) -> List[Dict]:
        """Возвращает список багов с определенным приоритетом"""
        return [bug for bug in self.bugs_data["bugs"] if bug["priority"] == priority.value]
    
    def get_pending_bugs(self) -> List[Dict]:
        """Возвращает список багов, ожидающих обработки"""
        pending_statuses = [BugStatus.REPORTED.value, BugStatus.ANALYZING.value]
        return [bug for bug in self.bugs_data["bugs"] if bug["status"] in pending_statuses]
    
    def get_critical_bugs(self) -> List[Dict]:
        """Возвращает список критических багов"""
        return [
            bug for bug in self.bugs_data["bugs"] 
            if bug["priority"] == BugPriority.CRITICAL.value 
            and bug["status"] not in [BugStatus.CLOSED.value, BugStatus.REJECTED.value]
        ]
    
    def get_statistics(self) -> Dict:
        """Возвращает статистику по багам"""
        stats = self.bugs_data.get("statistics", {})
        
        # Добавляем актуальную статистику
        current_stats = self._calculate_current_statistics()
        stats.update(current_stats)
        
        return stats
    
    def _find_bug_by_id(self, bug_id: str) -> Optional[Dict]:
        """Находит баг по ID"""
        for bug in self.bugs_data["bugs"]:
            if bug["id"] == bug_id:
                return bug
        return None
    
    def _generate_bug_id(self) -> str:
        """Генерирует уникальный ID для бага"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        existing_ids = [bug["id"] for bug in self.bugs_data["bugs"]]
        
        counter = 1
        while f"BR_{timestamp}_{counter:03d}" in existing_ids:
            counter += 1
        
        return f"BR_{timestamp}_{counter:03d}"
    
    def _determine_priority(self, bug_report: Dict, bug_analysis: Dict = None) -> str:
        """Определяет приоритет бага"""
        if bug_analysis:
            severity = bug_analysis.get('severity', 'normal')
            if severity == 'critical':
                return BugPriority.CRITICAL.value
            elif severity == 'high':
                return BugPriority.HIGH.value
        
        # Предложения всегда низкий приоритет
        if bug_report.get('type') == 'suggestion':
            return BugPriority.LOW.value
        
        # Анализируем проблемы по ключевым словам
        description = bug_report.get('description', '').lower()
        
        critical_keywords = ['не работает', 'крашится', 'не запускается', 'не отвечает', 'ошибка']
        high_keywords = ['не найдено', 'неправильно', 'зависает', 'медленно']
        
        if any(keyword in description for keyword in critical_keywords):
            return BugPriority.CRITICAL.value
        elif any(keyword in description for keyword in high_keywords):
            return BugPriority.HIGH.value
        else:
            return BugPriority.NORMAL.value
    
    def _generate_tags(self, bug_report: Dict, bug_analysis: Dict = None) -> List[str]:
        """Генерирует теги для бага"""
        tags = []
        
        description = bug_report.get('description', '').lower()
        
        # Теги по функциональности
        if any(word in description for word in ['запись', 'бронирование', 'слот']):
            tags.append('booking')
        if any(word in description for word in ['массаж', 'мастер']):
            tags.append('massage')
        if any(word in description for word in ['устройство', 'девайс', 'кресло']):
            tags.append('device')
        if any(word in description for word in ['кнопка', 'callback']):
            tags.append('ui')
        
        # Теги по типу проблемы
        if any(word in description for word in ['опечатка', 'текст']):
            tags.append('text')
        if any(word in description for word in ['gpt', 'описание']):
            tags.append('gpt')
        
        # Добавляем тип бага из анализа
        if bug_analysis:
            bug_type = bug_analysis.get('bug_type')
            if bug_type:
                tags.append(bug_type)
        
        return list(set(tags))  # Убираем дубликаты
    
    def _update_statistics(self):
        """Обновляет статистику"""
        self.bugs_data["statistics"].update(self._calculate_current_statistics())
        self.bugs_data["statistics"]["last_updated"] = datetime.now().isoformat()
    
    def _calculate_current_statistics(self) -> Dict:
        """Вычисляет текущую статистику"""
        bugs = self.bugs_data["bugs"]
        
        total_bugs = len(bugs)
        fixed_bugs = len([b for b in bugs if b["status"] == BugStatus.FIXED.value])
        closed_bugs = len([b for b in bugs if b["status"] == BugStatus.CLOSED.value])
        critical_bugs = len([b for b in bugs if b["priority"] == BugPriority.CRITICAL.value])
        auto_fixed = len([
            b for b in bugs 
            if any(attempt.get("method") == "automatic" and attempt.get("success") 
                  for attempt in b.get("fix_attempts", []))
        ])
        
        # Статистика по времени (последние 7 дней)
        week_ago = datetime.now() - timedelta(days=7)
        recent_bugs = [
            b for b in bugs 
            if datetime.fromisoformat(b["created_at"].replace('Z', '+00:00')) > week_ago
        ]
        
        return {
            "total_bugs": total_bugs,
            "fixed_bugs": fixed_bugs,
            "closed_bugs": closed_bugs,
            "critical_bugs": critical_bugs,
            "auto_fixed_bugs": auto_fixed,
            "pending_bugs": total_bugs - fixed_bugs - closed_bugs,
            "recent_bugs_7d": len(recent_bugs),
            "fix_rate": round(fixed_bugs / total_bugs * 100, 1) if total_bugs > 0 else 0
        }
    
    def cleanup_old_bugs(self, days: int = 30):
        """Очищает старые закрытые баги"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        original_count = len(self.bugs_data["bugs"])
        
        self.bugs_data["bugs"] = [
            bug for bug in self.bugs_data["bugs"]
            if not (
                bug["status"] in [BugStatus.CLOSED.value, BugStatus.REJECTED.value] and
                datetime.fromisoformat(bug["updated_at"].replace('Z', '+00:00')) < cutoff_date
            )
        ]
        
        cleaned_count = original_count - len(self.bugs_data["bugs"])
        
        if cleaned_count > 0:
            self._save_bugs_data()
            logger.info(f"🧹 Очищено {cleaned_count} старых багов")
        
        return cleaned_count

# Создаем глобальный экземпляр
bug_tracker = BugTracker()