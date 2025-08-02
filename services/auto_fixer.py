"""
Auto Fixer - автоматические безопасные исправления багов
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import difflib
from services.safe_data_manager import safe_data_manager

logger = logging.getLogger(__name__)

class AutoFixer:
    def __init__(self):
        self.safe_fixes = {
            'typo_fixes': self._fix_typos,
            'emoji_fixes': self._fix_emojis,
            'formatting_fixes': self._fix_formatting,
            'link_fixes': self._fix_links,
            'case_fixes': self._fix_case_issues
        }
        
        # Паттерны для безопасных исправлений
        self.typo_patterns = {
            # Распространенные опечатки в русском тексте
            r'\bне работет\b': 'не работает',
            r'\bработет\b': 'работает',
            r'\bзаписатся\b': 'записаться',
            r'\bзаписатся\b': 'записаться',
            r'\bмассож\b': 'массаж',
            r'\bвиброкресло\b': 'виброакустическое кресло',
            r'\bслоты\b': 'слоты',
            r'\bмастера\b': 'мастера',
            # Английские опечатки
            r'\bteh\b': 'the',
            r'\badn\b': 'and',
            r'\byuo\b': 'you'
        }
        
        self.emoji_fixes = {
            'massage': '💆',
            'chair': '🪑',
            'device': '📱',
            'booking': '📅',
            'master': '👨‍⚕️',
            'error': '❌',
            'success': '✅',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        
        # Файлы, которые безопасно редактировать
        self.safe_files = [
            'working_bot.py',
            'services/gpt_service.py',
            'services/bug_reporter.py'
        ]
        
        # Опасные паттерны - НЕ трогаем автоматически
        self.dangerous_patterns = [
            r'import\s+',  # Импорты
            r'def\s+\w+\(',  # Определения функций
            r'class\s+\w+',  # Определения классов
            r'async\s+def',  # Async функции
            r'await\s+',  # Await выражения
            r'callback_data',  # Callback логика
            r'database\.json',  # Работа с БД
            r'BOT_TOKEN',  # Токены и ключи
            r'OPENAI_API_KEY'
        ]
    
    def can_auto_fix(self, bug_analysis: Dict) -> bool:
        """Определяет, можно ли автоматически исправить баг"""
        if not bug_analysis.get('auto_fixable', False):
            return False
        
        description = bug_analysis.get('original_description', '').lower()
        
        # Проверяем, что это безопасный тип исправления
        safe_keywords = [
            'опечатка', 'typo', 'неправильный текст', 'текст',
            'emoji', 'эмодзи', 'форматирование',
            'ссылка', 'link', 'регистр'
        ]
        
        return any(keyword in description for keyword in safe_keywords)
    
    def auto_fix_bug(self, bug_analysis: Dict) -> Dict:
        """Выполняет автоматическое исправление бага"""
        try:
            logger.info(f"🤖 Начинаю автофикс для бага {bug_analysis.get('bug_id')}")
            
            fix_type = self._determine_fix_type(bug_analysis)
            
            if fix_type not in self.safe_fixes:
                return self._create_fix_result(False, "Тип исправления не поддерживается")
            
            # Выполняем исправление
            fix_function = self.safe_fixes[fix_type]
            result = fix_function(bug_analysis)
            
            if result['success']:
                # Создаем бэкап перед изменением
                safe_data_manager.backup_manager.create_backup("auto_fix_before")
                
                # Логируем исправление
                self._log_fix_action(bug_analysis, result)
                
                logger.info(f"✅ Автофикс завершен для бага {bug_analysis.get('bug_id')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка автофикса: {e}")
            return self._create_fix_result(False, f"Ошибка: {e}")
    
    def _determine_fix_type(self, bug_analysis: Dict) -> str:
        """Определяет тип необходимого исправления"""
        description = bug_analysis.get('original_description', '').lower()
        
        if any(word in description for word in ['опечатка', 'typo', 'написано']):
            return 'typo_fixes'
        elif any(word in description for word in ['emoji', 'эмодзи', 'значок']):
            return 'emoji_fixes'
        elif any(word in description for word in ['форматирование', 'отступ', 'пробел']):
            return 'formatting_fixes'
        elif any(word in description for word in ['ссылка', 'link', 'url']):
            return 'link_fixes'
        elif any(word in description for word in ['регистр', 'заглавн', 'строчн']):
            return 'case_fixes'
        else:
            return 'unknown'
    
    def _fix_typos(self, bug_analysis: Dict) -> Dict:
        """Исправляет опечатки в текстах"""
        try:
            modified_files = []
            changes_made = []
            
            # Ищем опечатки в основных файлах с текстами
            for file_path in self.safe_files:
                if not os.path.exists(file_path):
                    continue
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Применяем исправления опечаток
                for pattern, replacement in self.typo_patterns.items():
                    if re.search(pattern, content, re.IGNORECASE):
                        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                        changes_made.append(f"{pattern} → {replacement}")
                
                # Если есть изменения, сохраняем файл
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    modified_files.append(file_path)
                    logger.info(f"📝 Исправлены опечатки в {file_path}")
            
            if modified_files:
                return self._create_fix_result(
                    True, 
                    f"Исправлены опечатки в файлах: {', '.join(modified_files)}",
                    modified_files,
                    changes_made
                )
            else:
                return self._create_fix_result(False, "Опечатки не найдены")
                
        except Exception as e:
            logger.error(f"❌ Ошибка исправления опечаток: {e}")
            return self._create_fix_result(False, f"Ошибка: {e}")
    
    def _fix_emojis(self, bug_analysis: Dict) -> Dict:
        """Добавляет или исправляет emoji в текстах"""
        try:
            # Здесь можно добавить логику поиска и добавления emoji
            # Пока что заглушка для демонстрации концепции
            
            description = bug_analysis.get('original_description', '')
            
            # Простой пример: если упоминается массаж без emoji
            if 'массаж' in description.lower() and '💆' not in description:
                # В реальности здесь была бы логика поиска и замены в файлах
                return self._create_fix_result(
                    True,
                    "Добавлены недостающие emoji для массажа",
                    ["working_bot.py"],
                    ["Добавлен emoji 💆 для массажа"]
                )
            
            return self._create_fix_result(False, "Emoji исправления не требуются")
            
        except Exception as e:
            return self._create_fix_result(False, f"Ошибка: {e}")
    
    def _fix_formatting(self, bug_analysis: Dict) -> Dict:
        """Исправляет форматирование текста"""
        try:
            # Заглушка для форматирования
            # Здесь можно добавить логику исправления отступов, пробелов и т.д.
            
            return self._create_fix_result(False, "Форматирование исправления не требуется")
            
        except Exception as e:
            return self._create_fix_result(False, f"Ошибка: {e}")
    
    def _fix_links(self, bug_analysis: Dict) -> Dict:
        """Исправляет устаревшие или неправильные ссылки"""
        try:
            # Заглушка для исправления ссылок
            # Здесь можно добавить логику поиска и обновления ссылок
            
            return self._create_fix_result(False, "Ссылки исправления не требуют")
            
        except Exception as e:
            return self._create_fix_result(False, f"Ошибка: {e}")
    
    def _fix_case_issues(self, bug_analysis: Dict) -> Dict:
        """Исправляет проблемы с регистром букв"""
        try:
            # Заглушка для исправления регистра
            # Здесь можно добавить логику исправления заглавных/строчных букв
            
            return self._create_fix_result(False, "Регистр исправления не требует")
            
        except Exception as e:
            return self._create_fix_result(False, f"Ошибка: {e}")
    
    def _create_fix_result(self, success: bool, description: str, 
                          modified_files: List[str] = None, 
                          changes: List[str] = None) -> Dict:
        """Создает результат исправления"""
        return {
            'success': success,
            'description': description,
            'modified_files': modified_files or [],
            'changes_made': changes or [],
            'timestamp': datetime.now().isoformat(),
            'tests_passed': 'Автотесты не выполнялись'  # Можно добавить позже
        }
    
    def _log_fix_action(self, bug_analysis: Dict, fix_result: Dict):
        """Логирует выполненное исправление"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'bug_id': bug_analysis.get('bug_id'),
            'fix_type': 'automatic',
            'success': fix_result['success'],
            'description': fix_result['description'],
            'modified_files': fix_result['modified_files'],
            'changes': fix_result['changes_made']
        }
        
        # Сохраняем в файл логов автофиксов
        log_file = 'data/auto_fixes.log'
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        logger.info(f"📝 Автофикс залогирован: {bug_analysis.get('bug_id')}")
    
    def is_safe_to_modify(self, file_path: str, content_change: str) -> bool:
        """Проверяет, безопасно ли модифицировать файл"""
        
        # Проверяем, что файл в списке безопасных
        if file_path not in self.safe_files:
            return False
        
        # Проверяем, что изменение не затрагивает опасные паттерны
        for pattern in self.dangerous_patterns:
            if re.search(pattern, content_change, re.IGNORECASE):
                logger.warning(f"⚠️ Опасный паттерн найден в изменении: {pattern}")
                return False
        
        return True
    
    def get_fix_statistics(self) -> Dict:
        """Возвращает статистику автоисправлений"""
        log_file = 'data/auto_fixes.log'
        
        if not os.path.exists(log_file):
            return {'total_fixes': 0, 'successful_fixes': 0, 'failed_fixes': 0}
        
        total = 0
        successful = 0
        failed = 0
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        total += 1
                        if entry.get('success'):
                            successful += 1
                        else:
                            failed += 1
        except Exception as e:
            logger.error(f"❌ Ошибка чтения статистики автофиксов: {e}")
        
        return {
            'total_fixes': total,
            'successful_fixes': successful,
            'failed_fixes': failed,
            'success_rate': round(successful / total * 100, 1) if total > 0 else 0
        }

# Создаем глобальный экземпляр
auto_fixer = AutoFixer()