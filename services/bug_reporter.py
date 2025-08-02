#!/usr/bin/env python3
"""
Система автоматизированного сбора и анализа багов от пользователей
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

# Импорты новых компонентов (с обработкой circular imports)
try:
    from services.gpt_bug_analyzer import gpt_bug_analyzer
    from services.telegram_notifier import telegram_notifier
    from services.auto_fixer import auto_fixer
    from services.bug_tracker import bug_tracker
except ImportError as e:
    logging.warning(f"Некоторые компоненты недоступны: {e}")

logger = logging.getLogger(__name__)

class BugReporter:
    """Управляет сбором и анализом багов от пользователей."""
    
    def __init__(self, reports_file: str = "data/bug_reports.json"):
        self.reports_file = reports_file
        self.ensure_reports_file()
    
    def ensure_reports_file(self):
        """Создает файл для отчетов если его нет."""
        if not os.path.exists(self.reports_file):
            os.makedirs(os.path.dirname(self.reports_file), exist_ok=True)
            with open(self.reports_file, 'w', encoding='utf-8') as f:
                json.dump({"reports": []}, f, ensure_ascii=False, indent=2)
    
    async def handle_bug_report_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Начинает процесс сбора информации о баге."""
        keyboard = [
            [InlineKeyboardButton("🐛 Что-то не работает", callback_data="bug_problem")],
            [InlineKeyboardButton("💡 Предложение", callback_data="bug_suggestion")],
            [InlineKeyboardButton("❌ Отмена", callback_data="bug_cancel")]
        ]
        
        await update.message.reply_text(
            "🐛 **Сообщить о проблеме**\n\n"
            "Спасибо, что помогаешь улучшить бота! Выбери тип обращения:\n\n"
            "🐛 **Что-то не работает** - ошибка, баг, неправильное поведение\n"
            "💡 **Предложение** - идея для улучшения или новая функция\n\n"
            "Твой отчет поможет быстро исправить проблему!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_bug_type_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, bug_type: str) -> None:
        """Обрабатывает выбор типа бага."""
        query = update.callback_query
        await query.answer()
        
        user_id = str(update.effective_user.id)
        context.user_data['bug_report'] = {
            'type': bug_type,
            'user_id': user_id,
            'username': update.effective_user.username,
            'first_name': update.effective_user.first_name,
            'started_at': datetime.now().isoformat()
        }
        
        type_names = {
            'problem': '🐛 Проблема',
            'suggestion': '💡 Предложение'
        }
        
        if bug_type == 'problem':
            instruction_text = (
                f"📝 **{type_names.get(bug_type, 'Отчет')}**\n\n"
                "Опиши что случилось подробно:\n\n"
                "🎯 **ЧТО ТЫ ДЕЛАЛ:**\n"
                "(например: выбирал слот на завтра у Маши)\n\n"
                "❌ **ЧТО ПОШЛО НЕ ТАК:**\n"
                "(например: бот показал ошибку или зависает)\n\n"
                "✅ **ЧТО ОЖИДАЛ:**\n"
                "(например: должен был показать доступные слоты)\n\n"
                "🕐 **КОГДА:**\n"
                "(например: сегодня в 15:30)\n\n"
                "💡 **Если можешь - приложи СКРИНШОТ экрана!**\n"
                "Напиши все подряд одним сообщением или несколькими ⬇️"
            )
        else:  # suggestion
            instruction_text = (
                f"📝 **{type_names.get(bug_type, 'Отчет')}**\n\n"
                "Поделись своей идеей:\n\n"
                "💡 **ЧТО ПРЕДЛАГАЕШЬ:**\n"
                "(например: добавить напоминания за час до сеанса)\n\n"
                "🎯 **ЗАЧЕМ ЭТО НУЖНО:**\n"
                "(например: чтобы не забывать о записи)\n\n"
                "🔧 **КАК ВИДИШЬ РЕАЛИЗАЦИЮ:**\n"
                "(если есть идеи как это должно работать)\n\n"
                "Напиши свое предложение ⬇️"
            )
        
        await query.edit_message_text(
            instruction_text,
            parse_mode='Markdown'
        )
    
    async def handle_bug_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает описание бага от пользователя."""
        if 'bug_report' not in context.user_data:
            await update.message.reply_text("❌ Сначала нужно начать процесс сообщения о баге командой /bug")
            return
        
        description = update.message.text
        bug_report = context.user_data['bug_report']
        bug_report['description'] = description
        bug_report['completed_at'] = datetime.now().isoformat()
        
        # Генерируем уникальный ID для отчета
        report_id = f"BR_{int(datetime.now().timestamp())}"
        bug_report['report_id'] = report_id
        bug_report['id'] = report_id
        
        # Сохраняем отчет (старый формат для совместимости)
        await self._save_bug_report(bug_report)
        
        # НОВАЯ ФУНКЦИОНАЛЬНОСТЬ: Полная обработка бага
        await self._process_enhanced_bug_report(bug_report)
        
        # Отправляем подтверждение пользователю
        keyboard = [
            [InlineKeyboardButton("📋 Посмотреть мои отчеты", callback_data="bug_my_reports")]
        ]
        
        await update.message.reply_text(
            f"✅ **Отчет получен!**\n\n"
            f"🆔 Номер отчета: `{report_id}`\n"
            f"📝 Тип: {self._get_type_emoji(bug_report['type'])}\n\n"
            "Спасибо за обратную связь! Баг автоматически проанализирован.\n"
            "Если это критический баг, администратор получит немедленное уведомление!\n"
            "Ты получишь уведомление, когда баг будет исправлен.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Очищаем состояние
        del context.user_data['bug_report']
    
    async def _save_bug_report(self, report: Dict) -> None:
        """Сохраняет отчет о баге в файл."""
        try:
            # Загружаем существующие отчеты
            with open(self.reports_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Добавляем новый отчет
            data['reports'].append(report)
            
            # Сохраняем обновленные данные
            with open(self.reports_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📝 Сохранен отчет о баге: {report['report_id']}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения отчета о баге: {e}")
    
    async def _log_bug_for_admin(self, report: Dict) -> None:
        """Логирует баг для администратора."""
        priority = "🚨 КРИТИЧЕСКИЙ" if report['type'] == 'critical' else "📢 НОВЫЙ"
        
        logger.warning(f"{priority} БАГ РЕПОРТ:")
        logger.warning(f"  ID: {report['report_id']}")
        logger.warning(f"  Пользователь: {report.get('first_name', 'Неизвестно')} (@{report.get('username', 'нет')})")
        logger.warning(f"  Тип: {report['type']}")
        logger.warning(f"  Описание: {report['description'][:200]}...")
    
    def _get_type_emoji(self, bug_type: str) -> str:
        """Возвращает эмодзи для типа бага."""
        emojis = {
            'problem': '🐛 Проблема',
            'suggestion': '💡 Предложение'
        }
        return emojis.get(bug_type, '❓ Неизвестно')
    
    def get_recent_reports(self, hours: int = 24) -> List[Dict]:
        """Возвращает отчеты за последние N часов."""
        try:
            with open(self.reports_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cutoff_time = datetime.now().timestamp() - (hours * 3600)
            recent_reports = []
            
            for report in data.get('reports', []):
                try:
                    report_time = datetime.fromisoformat(report['completed_at']).timestamp()
                    if report_time > cutoff_time:
                        recent_reports.append(report)
                except:
                    continue
            
            return recent_reports
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки отчетов: {e}")
            return []
    
    def get_critical_reports(self) -> List[Dict]:
        """Возвращает все критические отчеты."""
        try:
            with open(self.reports_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            critical_reports = [
                report for report in data.get('reports', [])
                if report.get('type') == 'critical' and report.get('status', 'open') == 'open'
            ]
            
            return critical_reports
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки критических отчетов: {e}")
            return []
    
    async def mark_report_resolved(self, report_id: str, resolution: str) -> bool:
        """Помечает отчет как решенный."""
        try:
            with open(self.reports_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for report in data.get('reports', []):
                if report.get('report_id') == report_id:
                    report['status'] = 'resolved'
                    report['resolved_at'] = datetime.now().isoformat()
                    report['resolution'] = resolution
                    
                    with open(self.reports_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"✅ Отчет {report_id} помечен как решенный")
                    return True
            
            logger.warning(f"⚠️ Отчет {report_id} не найден")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления отчета: {e}")
            return False
    
    async def _process_enhanced_bug_report(self, bug_report: Dict) -> None:
        """Новая функциональность: полная обработка бага с анализом и уведомлениями"""
        try:
            logger.info(f"🔄 Начинаю расширенную обработку бага {bug_report['id']}")
            
            # 1. Анализируем баг через GPT
            try:
                bug_analysis = gpt_bug_analyzer.analyze_bug(bug_report)
                logger.info(f"🧠 GPT анализ завершен для {bug_report['id']}")
            except Exception as e:
                logger.error(f"❌ Ошибка GPT анализа: {e}")
                bug_analysis = self._create_fallback_analysis(bug_report)
            
            # 2. Регистрируем в трекере
            try:
                bug_tracker.register_bug(bug_report, bug_analysis)
                logger.info(f"📋 Баг зарегистрирован в трекере: {bug_report['id']}")
            except Exception as e:
                logger.error(f"❌ Ошибка регистрации в трекере: {e}")
            
            # 3. Проверяем возможность автофикса
            try:
                if auto_fixer.can_auto_fix(bug_analysis):
                    logger.info(f"🤖 Начинаю автофикс для {bug_report['id']}")
                    
                    fix_result = auto_fixer.auto_fix_bug(bug_analysis)
                    
                    if fix_result['success']:
                        # Логируем успешное исправление
                        bug_tracker.log_fix_attempt(bug_report['id'], fix_result, success=True)
                        
                        # Уведомляем администратора об автофиксе
                        telegram_notifier.send_auto_fix_notification(bug_report['id'], fix_result)
                        
                        logger.info(f"✅ Автофикс успешен для {bug_report['id']}")
                    else:
                        logger.info(f"❌ Автофикс неудачен для {bug_report['id']}: {fix_result['description']}")
                        
                        # Добавляем в очередь для ручного исправления
                        bug_analysis['original_description'] = bug_report['description']
                        bug_analysis['reporter'] = f"@{bug_report.get('username', 'unknown')}"
                        telegram_notifier.add_to_pending(bug_analysis)
                else:
                    # Добавляем в очередь для ручного исправления
                    bug_analysis['original_description'] = bug_report['description']
                    bug_analysis['reporter'] = f"@{bug_report.get('username', 'unknown')}"
                    telegram_notifier.add_to_pending(bug_analysis)
                    
                    logger.info(f"📝 Баг {bug_report['id']} добавлен в очередь для ручного исправления")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка обработки автофикса: {e}")
                
                # В случае ошибки все равно добавляем в очередь
                bug_analysis['original_description'] = bug_report['description']
                bug_analysis['reporter'] = f"@{bug_report.get('username', 'unknown')}"
                telegram_notifier.add_to_pending(bug_analysis)
            
            logger.info(f"✅ Расширенная обработка бага {bug_report['id']} завершена")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка обработки бага {bug_report.get('id', 'unknown')}: {e}")
    
    def _create_fallback_analysis(self, bug_report: Dict) -> Dict:
        """Создает базовый анализ в случае ошибки GPT"""
        # Все проблемы (не предложения) считаем серьезными
        severity = 'high' if bug_report.get('type') == 'problem' else 'normal'
        
        return {
            'bug_id': bug_report['id'],
            'analyzed_at': datetime.now().isoformat(),
            'bug_type': 'unknown',
            'severity': severity,
            'analysis': 'GPT анализ недоступен. Требуется ручной анализ.',
            'cursor_prompt': f'Исследуй проблему: {bug_report.get("description", "")}',
            'auto_fixable': False,
            'estimated_complexity': 'unknown',
            'affected_files': ['working_bot.py'],
            'test_scenarios': ['Воспроизвести описанную проблему']
        }
    
    def get_enhanced_statistics(self) -> Dict:
        """Возвращает расширенную статистику по багам"""
        try:
            # Статистика из старого формата
            basic_stats = {
                'total_reports': 0,
                'critical_reports': 0,
                'recent_reports_24h': 0
            }
            
            try:
                recent_reports = self.get_recent_reports(24)
                critical_reports = self.get_critical_reports()
                
                with open(self.reports_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                basic_stats.update({
                    'total_reports': len(data.get('reports', [])),
                    'critical_reports': len(critical_reports),
                    'recent_reports_24h': len(recent_reports)
                })
            except Exception as e:
                logger.error(f"❌ Ошибка базовой статистики: {e}")
            
            # Статистика из нового трекера
            try:
                tracker_stats = bug_tracker.get_statistics()
                basic_stats.update(tracker_stats)
            except Exception as e:
                logger.error(f"❌ Ошибка статистики трекера: {e}")
            
            # Статистика автофиксов
            try:
                autofix_stats = auto_fixer.get_fix_statistics()
                basic_stats.update({
                    'auto_fixes_total': autofix_stats.get('total_fixes', 0),
                    'auto_fixes_successful': autofix_stats.get('successful_fixes', 0),
                    'auto_fix_success_rate': autofix_stats.get('success_rate', 0)
                })
            except Exception as e:
                logger.error(f"❌ Ошибка статистики автофиксов: {e}")
            
            return basic_stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения расширенной статистики: {e}")
            return {'error': str(e)}

# Глобальный экземпляр репортера
bug_reporter = BugReporter()