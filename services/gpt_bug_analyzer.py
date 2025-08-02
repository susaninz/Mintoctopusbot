"""
GPT Bug Analyzer - анализирует багрепорты и генерирует промпты для Cursor
"""

import openai
import logging
from typing import Dict, List, Optional
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)

class GPTBugAnalyzer:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.codebase_context = self._load_codebase_context()
        
    def _load_codebase_context(self) -> str:
        """Загружает контекст кодбейза для лучшего анализа"""
        context = """
        КОНТЕКСТ КОДБЕЙЗА MINTOCTOPUS BOT:
        
        Основные файлы:
        - working_bot.py: главная логика бота, обработчики команд и callback
        - services/data_manager.py: управление JSON базой данных
        - services/gpt_service.py: интеграция с GPT для описаний и анализа
        - services/bug_reporter.py: система багрепортов
        - data/database.json: JSON база с мастерами, устройствами, записями
        
        Основные функции:
        - handle_callback_query: обработка нажатий кнопок
        - show_device_details: показ информации об устройствах
        - process_device_booking: обработка бронирования устройств
        - show_slots_with_management: управление слотами мастеров
        
        Типичные проблемы:
        - Парсинг callback_data с подчеркиваниями (device_id)
        - Async/await issues в обработчиках
        - Время и дата в слотах (past/future filtering)
        - GPT температура и точность описаний
        - Healthcheck и webhook настройка
        """
        return context
        
    def analyze_bug(self, bug_report: Dict) -> Dict:
        """
        Анализирует багрепорт и возвращает структурированный анализ
        """
        try:
            logger.info(f"🔍 Анализирую баг ID: {bug_report.get('id', 'unknown')}")
            
            # Классифицируем тип бага
            bug_type = self._classify_bug_type(bug_report)
            severity = self._determine_severity(bug_report)
            
            # Генерируем анализ через GPT
            analysis = self._generate_gpt_analysis(bug_report, bug_type)
            
            # Создаем промпт для Cursor
            cursor_prompt = self._generate_cursor_prompt(bug_report, analysis)
            
            # Определяем возможность автофикса
            auto_fixable = self._is_auto_fixable(bug_report, analysis)
            
            result = {
                "bug_id": bug_report.get('id'),
                "analyzed_at": datetime.now().isoformat(),
                "bug_type": bug_type,
                "severity": severity,
                "analysis": analysis,
                "cursor_prompt": cursor_prompt,
                "auto_fixable": auto_fixable,
                "estimated_complexity": self._estimate_complexity(analysis),
                "affected_files": self._identify_affected_files(analysis),
                "test_scenarios": self._suggest_test_scenarios(bug_report)
            }
            
            logger.info(f"✅ Анализ завершен. Тип: {bug_type}, Серьезность: {severity}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа бага: {e}")
            return self._create_fallback_analysis(bug_report)
    
    def _classify_bug_type(self, bug_report: Dict) -> str:
        """Классифицирует тип бага по описанию"""
        description = bug_report.get('description', '').lower()
        
        if any(word in description for word in ['не работает', 'не отвечает', 'зависает']):
            return "functionality_failure"
        elif any(word in description for word in ['ошибка', 'error', 'не найдено']):
            return "error_message"
        elif any(word in description for word in ['медленно', 'долго', 'тормозит']):
            return "performance"
        elif any(word in description for word in ['неправильно', 'некорректно', 'не то']):
            return "incorrect_behavior"
        elif any(word in description for word in ['не показывает', 'пропал', 'отсутствует']):
            return "missing_data"
        else:
            return "other"
    
    def _determine_severity(self, bug_report: Dict) -> str:
        """Определяет серьезность бага"""
        report_type = bug_report.get('type', '')
        description = bug_report.get('description', '').lower()
        
        # Предложения всегда низкий приоритет
        if report_type == 'suggestion':
            return "normal"
        
        # Для проблем анализируем по ключевым словам
        critical_keywords = ['не работает', 'не запускается', 'крашится', 'не отвечает', 'ошибка', 'зависает']
        if any(word in description for word in critical_keywords):
            return "critical"
        
        # Высокий приоритет для основных функций
        if any(word in description for word in ['запись', 'бронирование', 'слоты', 'мастер']):
            return "high"
        else:
            return "normal"
    
    def _generate_gpt_analysis(self, bug_report: Dict, bug_type: str) -> str:
        """Генерирует анализ через GPT"""
        try:
            prompt = f"""
            Ты эксперт по отладке Telegram ботов на Python. Проанализируй багрепорт:
            
            ОПИСАНИЕ ПРОБЛЕМЫ: {bug_report.get('description', '')}
            ТИП БАГА: {bug_type}
            ШАГИ ВОСПРОИЗВЕДЕНИЯ: {bug_report.get('steps_to_reproduce', 'Не указаны')}
            
            КОНТЕКСТ КОДБЕЙЗА:
            {self.codebase_context}
            
            Проведи анализ и определи:
            1. Наиболее вероятную причину проблемы
            2. В каком файле/функции искать проблему
            3. Что конкретно может быть не так
            4. Связанные компоненты, которые тоже нужно проверить
            
            Ответь кратко и конкретно, фокусируясь на технических деталях.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Низкая температура для точности
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ Ошибка GPT анализа: {e}")
            return f"GPT анализ недоступен. Ручной анализ: {bug_type}"
    
    def _generate_cursor_prompt(self, bug_report: Dict, analysis: str) -> str:
        """Генерирует промпт для Cursor IDE"""
        cursor_prompt = f"""
        🐛 БАГФИКС ИНСТРУКЦИЯ ДЛЯ CURSOR

        📋 ПРОБЛЕМА:
        {bug_report.get('description', '')}
        
        🔍 GPT АНАЛИЗ:
        {analysis}
        
        💻 ЧТО ДЕЛАТЬ В CURSOR:
        1. Открой файл с наиболее вероятной проблемой
        2. Найди функцию/раздел, упомянутый в анализе
        3. Проверь логику обработки данных
        4. Обрати внимание на async/await и error handling
        5. Проверь парсинг callback_data если проблема с кнопками
        
        🎯 ФОКУС НА:
        - Обработка edge cases
        - Правильность условий if/else
        - Корректность парсинга строк и данных
        - Проверка существования объектов перед использованием
        
        ✅ ПОСЛЕ ИСПРАВЛЕНИЯ ПРОВЕРЬ:
        - Тот же сценарий, который вызвал баг
        - Похожие функции с аналогичной логикой
        - Логи на предмет новых ошибок
        """
        
        return cursor_prompt
    
    def _is_auto_fixable(self, bug_report: Dict, analysis: str) -> bool:
        """Определяет, можно ли автоматически исправить баг"""
        description = bug_report.get('description', '').lower()
        
        # Безопасные для автофикса проблемы
        safe_fixes = [
            'опечатка', 'typo', 'неправильный текст',
            'неправильная ссылка', 'устаревшая ссылка',
            'форматирование', 'регистр букв',
            'отсутствует emoji', 'неправильный emoji'
        ]
        
        return any(fix in description for fix in safe_fixes)
    
    def _estimate_complexity(self, analysis: str) -> str:
        """Оценивает сложность исправления"""
        analysis_lower = analysis.lower()
        
        if any(word in analysis_lower for word in ['простая', 'опечатка', 'текст']):
            return "low"
        elif any(word in analysis_lower for word in ['логика', 'условие', 'парсинг']):
            return "medium"
        elif any(word in analysis_lower for word in ['архитектура', 'рефакторинг', 'база данных']):
            return "high"
        else:
            return "medium"
    
    def _identify_affected_files(self, analysis: str) -> List[str]:
        """Извлекает список файлов из анализа"""
        files = []
        common_files = [
            'working_bot.py', 'data_manager.py', 'gpt_service.py',
            'bug_reporter.py', 'database.json'
        ]
        
        for file in common_files:
            if file in analysis:
                files.append(file)
        
        return files if files else ['working_bot.py']  # По умолчанию основной файл
    
    def _suggest_test_scenarios(self, bug_report: Dict) -> List[str]:
        """Предлагает сценарии для тестирования после исправления"""
        scenarios = [
            "Повторить точные шаги из багрепорта",
            "Проверить аналогичную функциональность",
            "Тестировать edge cases"
        ]
        
        # Добавляем специфичные сценарии на основе типа бага
        description = bug_report.get('description', '').lower()
        if 'кнопк' in description:
            scenarios.append("Протестировать все кнопки в том же разделе")
        if 'устройство' in description:
            scenarios.append("Проверить бронирование других устройств")
        if 'слот' in description:
            scenarios.append("Проверить отображение слотов на разные даты")
            
        return scenarios
    
    def _create_fallback_analysis(self, bug_report: Dict) -> Dict:
        """Создает базовый анализ в случае ошибки"""
        return {
            "bug_id": bug_report.get('id'),
            "analyzed_at": datetime.now().isoformat(),
            "bug_type": "unknown",
            "severity": "normal",
            "analysis": "Автоматический анализ недоступен. Требуется ручной анализ.",
            "cursor_prompt": f"Исследуй проблему: {bug_report.get('description', '')}",
            "auto_fixable": False,
            "estimated_complexity": "unknown",
            "affected_files": ["working_bot.py"],
            "test_scenarios": ["Воспроизвести описанную проблему"]
        }

# Создаем глобальный экземпляр
gpt_bug_analyzer = GPTBugAnalyzer()