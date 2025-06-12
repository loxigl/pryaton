import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from telegram.ext import Application
import pytz

from src.models.base import get_db
from src.models.game import Game, GameStatus, GameParticipant, GameRole
from src.models.scheduled_event import ScheduledEvent, EventType
from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.event_persistence_service import EventPersistenceService
from src.services.settings_service import SettingsService


# Определяем временную зону (по умолчанию московское время)
DEFAULT_TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "Europe/Moscow"))

def format_msk_time(dt: datetime) -> str:
    """Форматирует время в МСК"""
    if dt.tzinfo is None:
        dt = DEFAULT_TIMEZONE.localize(dt)
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%H:%M')

def format_msk_datetime(dt: datetime) -> str:
    """Форматирует дату и время в МСК"""
    if dt.tzinfo is None:
        dt = DEFAULT_TIMEZONE.localize(dt)
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%d.%m.%Y в %H:%M')

class EnhancedSchedulerService:
    """Улучшенный сервис планировщика с персистентными событиями"""
    
    def __init__(self, application: Application):
        # Инициализируем планировщик с правильной временной зоной
        self.scheduler = AsyncIOScheduler(timezone=DEFAULT_TIMEZONE)
        self.application = application
        self.bot = application.bot
        self.format_msk_time=format_msk_time
        # Настройки из переменных окружения
        self.hiding_time = int(os.getenv("HIDING_TIME", 30))  # минуты
        self.reminder_times = [int(x) for x in os.getenv("REMINDER_BEFORE_GAME", "60,24,5").split(",")]  # минуты
        self.hiding_warning_time = int(os.getenv("HIDING_WARNING_TIME", 5))  # за сколько минут предупреждать о конце пряток
        
        logger.info(f"Планировщик инициализирован с временной зоной: {DEFAULT_TIMEZONE}")
        
        self.event_persistence = EventPersistenceService()
        db_generator = get_db()
        self.db = next(db_generator)
    
    def start(self):
        """Запуск планировщика с восстановлением событий"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Планировщик задач запущен")
            
            # Восстанавливаем события из БД
            self._restore_events_from_db()
    
    def shutdown(self):
        """Остановка планировщика"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик задач остановлен")
    
    def _restore_events_from_db(self):
        """Восстановление всех незавершенных событий из базы данных"""
        try:
            events = EventPersistenceService.get_pending_events()
            restored_count = 0
            
            for event in events:
                # Проверяем, не просрочено ли событие
                if event.is_overdue:
                    logger.warning(f"Событие {event.id} просрочено, пропускаем: {event}")
                    continue
                
                # Планируем событие
                if self._schedule_event_from_db(event):
                    restored_count += 1
            
            logger.info(f"Восстановлено {restored_count} событий из {len(events)} найденных")
            
        except Exception as e:
            logger.error(f"Ошибка восстановления событий: {e}")
    
    def _schedule_event_from_db(self, event: ScheduledEvent) -> bool:
        """Планирование события из БД"""
        try:
            # Убеждаемся, что время события имеет правильную временную зону
            scheduled_time = event.scheduled_at
            if scheduled_time.tzinfo is None:
                # Если timezone не указан, считаем что это московское время
                scheduled_time = DEFAULT_TIMEZONE.localize(scheduled_time)
            elif scheduled_time.tzinfo != DEFAULT_TIMEZONE:
                # Конвертируем в нашу временную зону
                scheduled_time = scheduled_time.astimezone(DEFAULT_TIMEZONE)
            
            # Определяем функцию для выполнения
            if event.event_type.startswith("reminder_"):
                minutes = int(event.event_type.split("_")[1].replace("min", "").replace("hour", ""))
                if "hour" in event.event_type:
                    minutes *= 60
                func = self.send_game_reminder
                args = [event.game_id, minutes, event.id]
            elif event.event_type == "game_start":
                func = self.start_game
                args = [event.game_id, event.id]
            elif event.event_type == "hiding_phase_end":
                func = self.end_hiding_phase
                args = [event.game_id, event.id]
            elif event.event_type == "hiding_warning":
                func = self.send_hiding_warning
                args = [event.game_id, event.id]
            elif event.event_type == "search_phase_end":
                func = self.end_search_phase
                args = [event.game_id, event.id]
            elif event.event_type == "game_cleanup":
                func = self.cleanup_game
                args = [event.game_id, event.id]
            else:
                logger.warning(f"Неизвестный тип события: {event.event_type}")
                return False
            
            # Планируем событие с правильным временем
            self.scheduler.add_job(
                func,
                trigger=DateTrigger(run_date=scheduled_time),
                args=args,
                id=event.job_id,
                replace_existing=True
            )
            
            logger.debug(f"Восстановлено событие: {event.job_id} на {scheduled_time}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка планирования события {event.id}: {e}")
            return False
    
    def schedule_game_reminders(self, game_id: int):
        """Планирование напоминаний для игры с сохранением в БД"""
        game = GameService.get_game_by_id(game_id)
        if not game:
            logger.error(f"Игра {game_id} не найдена при планировании напоминаний")
            return
        
        # Убеждаемся, что время игры имеет правильную временную зону
        game_time = game.scheduled_at
        if game_time.tzinfo is None:
            game_time = DEFAULT_TIMEZONE.localize(game_time)
        elif game_time.tzinfo != DEFAULT_TIMEZONE:
            game_time = game_time.astimezone(DEFAULT_TIMEZONE)
        
        # Получаем текущее время в правильной временной зоне
        current_time = datetime.now(DEFAULT_TIMEZONE)
        
        # Планируем напоминания
        for reminder_minutes in self.reminder_times:
            reminder_time = game_time - timedelta(minutes=reminder_minutes)
            
            # Проверяем, что время напоминания еще не прошло
            if reminder_time > current_time:
                # Определяем тип события
                if reminder_minutes >= 60:
                    event_type = f"reminder_{reminder_minutes // 60}hour"
                else:
                    event_type = f"reminder_{reminder_minutes}min"
                
                # Сохраняем в БД
                event = EventPersistenceService.save_event(
                    game_id=game_id,
                    event_type=event_type,
                    scheduled_at=reminder_time.replace(tzinfo=None),  # Убираем timezone для БД
                    event_data={"minutes_before": reminder_minutes}
                )
                
                if event:
                    # Планируем в планировщике
                    self.scheduler.add_job(
                        self.send_game_reminder,
                        trigger=DateTrigger(run_date=reminder_time),
                        args=[game_id, reminder_minutes, event.id],
                        id=event.job_id,
                        replace_existing=True
                    )
                    
                    logger.info(f"Запланировано напоминание для игры {game_id} за {reminder_minutes} минут: {reminder_time}")
            else:
                logger.debug(f"Напоминание за {reminder_minutes} минут для игры {game_id} пропущено (время уже прошло)")
        
        # Планируем начало игры (фазу пряток)
        if game_time > current_time:
            start_event = EventPersistenceService.save_event(
                game_id=game_id,
                event_type="game_start",
                scheduled_at=game_time.replace(tzinfo=None),  # Убираем timezone для БД
                event_data={}
            )
            
            if start_event:
                self.scheduler.add_job(
                    self.start_game,
                    trigger=DateTrigger(run_date=game_time),
                    args=[game_id, start_event.id],
                    id=start_event.job_id,
                    replace_existing=True
                )
                
                logger.info(f"Запланирован автоматический старт игры {game_id}: {game_time}")
        
        # Планируем предупреждение за 5 минут до конца пряток
        hiding_warning_time = game_time + timedelta(minutes=self.hiding_time - self.hiding_warning_time)
        if hiding_warning_time > current_time:
            warning_event = EventPersistenceService.save_event(
                game_id=game_id,
                event_type="hiding_warning",
                scheduled_at=hiding_warning_time.replace(tzinfo=None),
                event_data={"warning_minutes": self.hiding_warning_time}
            )
            
            if warning_event:
                self.scheduler.add_job(
                    self.send_hiding_warning,
                    trigger=DateTrigger(run_date=hiding_warning_time),
                    args=[game_id, warning_event.id],
                    id=warning_event.job_id,
                    replace_existing=True
                )
                
                logger.info(f"Запланировано предупреждение о конце пряток для игры {game_id}: {hiding_warning_time}")
        
        # Планируем окончание фазы пряток (начало поиска)
        hiding_end_time = game_time + timedelta(minutes=self.hiding_time)
        if hiding_end_time > current_time:
            hiding_event = EventPersistenceService.save_event(
                game_id=game_id,
                event_type="hiding_phase_end",
                scheduled_at=hiding_end_time.replace(tzinfo=None),  # Убираем timezone для БД
                event_data={"hiding_time": self.hiding_time}
            )
            
            if hiding_event:
                self.scheduler.add_job(
                    self.end_hiding_phase,
                    trigger=DateTrigger(run_date=hiding_end_time),
                    args=[game_id, hiding_event.id],
                    id=hiding_event.job_id,
                    replace_existing=True
                )
                
                logger.info(f"Запланировано окончание пряток для игры {game_id}: {hiding_end_time}")

    def cancel_game_jobs(self, game_id: int):
        """Отмена всех задач для игры"""
        jobs_to_remove = []
        
        # Находим все задачи для данной игры
        for job in self.scheduler.get_jobs():
            if str(game_id) in job.id:
                jobs_to_remove.append(job.id)
        
        # Удаляем задачи из планировщика
        for job_id in jobs_to_remove:
            try:
                self.scheduler.remove_job(job_id)
                logger.info(f"Отменена задача {job_id} для игры {game_id}")
            except Exception as e:
                logger.error(f"Ошибка отмены задачи {job_id}: {e}")
        
        # Помечаем события в БД как отмененные
        try:
            EventPersistenceService.cancel_game_events(game_id)
        except Exception as e:
            logger.error(f"Ошибка отмены событий в БД для игры {game_id}: {e}")
    
    def get_scheduled_events_info(self) -> dict:
        """Получение информации о запланированных событиях"""
        try:
            # Получаем события из БД
            all_events = EventPersistenceService.get_all_events()
            pending_events = EventPersistenceService.get_pending_events()
            
            # Группируем по играм
            events_by_game = {}
            for event in pending_events:
                if event.game_id not in events_by_game:
                    events_by_game[event.game_id] = []
                events_by_game[event.game_id].append(event)
            
            # Статистика
            stats = {
                'total': len(all_events),
                'pending': len(pending_events),
                'executed': len([e for e in all_events if e.is_executed]),
                'overdue': len([e for e in all_events if e.is_overdue])
            }
            
            # Количество задач в планировщике
            scheduler_jobs_count = len(self.scheduler.get_jobs())
            
            return {
                'events_by_game': events_by_game,
                'statistics': stats,
                'scheduler_jobs': scheduler_jobs_count
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о событиях: {e}")
            return {
                'events_by_game': {},
                'statistics': {'total': 0, 'pending': 0, 'executed': 0, 'overdue': 0},
                'scheduler_jobs': 0
            }
    
    async def send_game_reminder(self, game_id: int, minutes_before: int, event_id: Optional[int] = None):
        """Отправка напоминания о игре"""
        try:
            game = GameService.get_game_by_id(game_id)
            if not game:
                return
            
            # Формируем текст напоминания
            reminder_text = (
                f"🔔 <b>Напоминание о игре!</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"⏰ <b>Начало:</b> {self.format_msk_datetime(game.scheduled_at)}\n"
                f"👥 <b>Участников:</b> {len(game.participants)}/{game.max_participants}\n\n"
            )
            
            # Добавляем информацию о времени до начала
            if minutes_before >= 60:
                hours = minutes_before // 60
                reminder_text += f"До начала осталось: <b>{hours} час(ов)</b>"
            else:
                reminder_text += f"До начала осталось: <b>{minutes_before} минут</b>"
            
            # Отправляем напоминание всем участникам
            sent_count = 0
            for participant in game.participants:
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=reminder_text,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка отправки напоминания пользователю {user.telegram_id}: {e}")
            
            # Уведомляем админов
            admins = UserService.get_admin_users()
            for admin in admins:
                try:
                    admin_text = (
                        f"👨‍💼 <b>Админ-уведомление: Напоминание отправлено</b>\n\n"
                        f"🎮 <b>Игра:</b> {game.district} (ID: {game.id})\n"
                        f"⏰ <b>Время:</b> {self.format_msk_datetime(game.scheduled_at)}\n"
                        f"👥 <b>Участников:</b> {len(game.participants)}\n\n"
                        f"📊 Отправлено напоминаний: {sent_count}"
                    )
                    
                    await self.bot.send_message(
                        chat_id=admin.telegram_id,
                        text=admin_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка уведомления админа {admin.telegram_id}: {e}")
            
            logger.info(f"Отправлены напоминания для игры {game_id} ({sent_count} участников)")
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания для игры {game_id}: {e}")
    
    async def start_game(self, game_id: int, event_id: int, start_type: str = "auto"):
        """Запуск игры с уведомлениями - начинает фазу пряток"""
        try:
            # Отмечаем событие как выполненное
            EventPersistenceService.mark_event_executed(event_id)
            
            game = GameService.get_game_by_id(game_id)
            if not game:
                logger.error(f"Игра {game_id} не найдена при запуске")
                return
            
            if game.status != GameStatus.UPCOMING:
                logger.info(f"Игра {game_id} имеет статус {game.status}, пропускаем запуск")
                return
            
            # Проверяем количество участников
            if len(game.participants) < 2:
                # Недостаточно участников - отменяем игру
                GameService.cancel_game(game_id, "Недостаточно участников")
                await self.notify_game_cancelled(game_id, "Недостаточно участников")
                return
            
            # Распределяем роли
            GameService.assign_roles(game_id)
            
            # Запускаем игру (переводим в фазу пряток)
            if GameService._start_game_internal(game_id):
                await self.notify_game_started(game_id, start_type)
                logger.info(f"Игра {game_id} запущена - фаза пряток началась ({start_type})")
            else:
                logger.error(f"Ошибка запуска игры {game_id}")
                
        except Exception as e:
            logger.error(f"Ошибка запуска игры {game_id}: {e}")
    
    async def send_hiding_warning(self, game_id: int, event_id: int):
        """Отправка предупреждения за 5 минут до конца пряток"""
        try:
            # Отмечаем событие как выполненное
            EventPersistenceService.mark_event_executed(event_id)
            
            game = GameService.get_game_by_id(game_id)
            if not game or game.status != GameStatus.HIDING_PHASE:
                logger.info(f"Игра {game_id} не в фазе пряток, пропускаем предупреждение")
                return
            
            # Получаем статистику не спрятавшихся водителей
            hiding_stats = GameService.get_hiding_stats(game_id)
            not_hidden_drivers = hiding_stats['not_hidden_drivers']
            
            if not_hidden_drivers:
                # Уведомляем не спрятавшихся водителей
                warning_text = (
                    f"⚠️ <b>Внимание! Осталось {self.hiding_warning_time} минут до конца пряток!</b>\n\n"
                    f"🎮 <b>Игра:</b> {game.district}\n\n"
                    f"🚗 Вы еще не отправили фото места пряток!\n"
                    f"📸 Срочно отправьте фотографию, иначе вы будете дисквалифицированы."
                )
                
                for driver in not_hidden_drivers:
                    user, _ = UserService.get_user_by_id(driver.user_id)
                    if user:
                        try:
                            await self.bot.send_message(
                                chat_id=user.telegram_id,
                                text=warning_text,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(f"Ошибка отправки предупреждения водителю {user.telegram_id}: {e}")
                
                # Уведомляем админов о статистике
                await self.notify_admins_hiding_stats(game_id, not_hidden_drivers)
                
                logger.info(f"Отправлены предупреждения {len(not_hidden_drivers)} не спрятавшимся водителям в игре {game_id}")
            else:
                logger.info(f"Все водители спрятались в игре {game_id}, предупреждения не нужны")
            
        except Exception as e:
            logger.error(f"Ошибка отправки предупреждений о конце пряток для игры {game_id}: {e}")
    
    async def notify_admins_hiding_stats(self, game_id: int, not_hidden_drivers: List):
        """Уведомление админов о статистике пряток"""
        try:
            admins = UserService.get_admin_users()
            if not admins:
                return
            
            game = GameService.get_game_by_id(game_id)
            if not game:
                return
            
            hiding_stats = GameService.get_hiding_stats(game_id)
            
            if not_hidden_drivers:
                not_hidden_names = []
                for driver in not_hidden_drivers:
                    user, _ = UserService.get_user_by_id(driver.user_id)
                    name = user.name if user else f"ID {driver.user_id}"
                    not_hidden_names.append(name)
                
                stats_text = (
                    f"⚠️ <b>Статистика пряток #{game_id}</b>\n\n"
                    f"🎮 <b>Игра:</b> {game.district}\n"
                    f"⏰ <b>Осталось времени:</b> {self.hiding_warning_time} минут\n\n"
                    f"🚗 <b>Водители:</b> {hiding_stats['total_drivers']}\n"
                    f"✅ Спрятались: {hiding_stats['hidden_count']}\n"
                    f"⚠️ НЕ спрятались: {hiding_stats['not_hidden_count']}\n\n"
                    f"<b>Не спрятавшиеся водители:</b>\n" +
                    "\n".join(f"• {name}" for name in not_hidden_names)
                )
            else:
                stats_text = (
                    f"✅ <b>Все водители спрятались! #{game_id}</b>\n\n"
                    f"🎮 <b>Игра:</b> {game.district}\n"
                    f"🚗 <b>Водители:</b> {hiding_stats['total_drivers']}\n"
                    f"⏰ <b>Осталось времени:</b> {self.hiding_warning_time} минут"
                )
            
            for admin in admins:
                try:
                    await self.bot.send_message(
                        chat_id=admin.telegram_id,
                        text=stats_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки статистики админу {admin.telegram_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка уведомления админов о статистике: {e}")
    
    async def end_hiding_phase(self, game_id: int, event_id: int):
        """Завершение фазы прятки - переход к фазе поиска"""
        try:
            # Отмечаем событие как выполненное
            EventPersistenceService.mark_event_executed(event_id)
            
            game = GameService.get_game_by_id(game_id)
            if not game or game.status != GameStatus.HIDING_PHASE:
                logger.info(f"Игра {game_id} не в фазе пряток, пропускаем завершение прятки")
                return
            
            # Переводим игру в фазу поиска
            GameService.start_searching_phase(game_id)
            
            hiding_end_text = (
                f"⏰ <b>Время пряток истекло!</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"🏁 <b>Фаза поиска началась!</b>\n\n"
            )
            
            # Уведомляем водителей
            drivers_text = hiding_end_text + (
                f"🚗 <b>Водители:</b> Время пряток закончилось!\n"
                f"Теперь вас могут искать. Удачи!"
            )
            
            # Уведомляем искателей
            seekers_text = hiding_end_text + (
                f"🔍 <b>Искатели:</b> Начинайте поиск!\n"
                f"📸 Отправляйте фотографии найденных машин с указанием водителя."
            )
            
            sent_count = 0
            for participant in game.participants:
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        if participant.role == GameRole.DRIVER:
                            text = drivers_text
                        else:
                            text = seekers_text
                        
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=text,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка уведомления об окончании пряток пользователю {user.telegram_id}: {e}")
            
            logger.info(f"Завершена фаза пряток для игры {game_id}, начата фаза поиска ({sent_count} уведомлений)")
            
        except Exception as e:
            logger.error(f"Ошибка завершения фазы пряток для игры {game_id}: {e}")
    
    async def end_search_phase(self, game_id: int, event_id: int):
        """Завершение фазы поиска (автоматическое завершение игры)"""
        try:
            # Отмечаем событие как выполненное
            EventPersistenceService.mark_event_executed(event_id)
            
            game = GameService.get_game_by_id(game_id)
            if not game or game.status != GameStatus.SEARCHING_PHASE:
                logger.info(f"Игра {game_id} не в фазе поиска, пропускаем завершение поиска")
                return
            
            # Завершаем игру принудительно
            if GameService.end_game(game_id):
                await self.notify_game_ended(game_id, "Время истекло")
                logger.info(f"Игра {game_id} автоматически завершена по времени")
            
        except Exception as e:
            logger.error(f"Ошибка завершения поиска для игры {game_id}: {e}")
    
    async def cleanup_game(self, game_id: int, event_id: int):
        """Очистка данных игры"""
        try:
            # Отмечаем событие как выполненное
            EventPersistenceService.mark_event_executed(event_id)
            
            # Здесь можно добавить логику очистки старых данных игры
            logger.info(f"Очистка данных для игры {game_id}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки данных игры {game_id}: {e}")
    
    async def notify_game_started(self, game_id: int, start_type: str = "auto"):
        """Уведомление о начале фазы пряток"""
        try:
            game = GameService.get_game_by_id(game_id)
            if not game:
                return
            
            # Формируем текст в зависимости от типа запуска
            if start_type == "auto":
                start_text = f"🚀 <b>Игра началась автоматически!</b>\n\n"
            elif start_type == "manual":
                start_text = f"🚀 <b>Игра запущена администратором!</b>\n\n"
            elif start_type == "early":
                start_text = f"⚡ <b>Игра начинается досрочно!</b>\n\n"
            else:
                start_text = f"🚀 <b>Игра началась!</b>\n\n"
            
            current_time = datetime.now(DEFAULT_TIMEZONE)
            
            start_text += (
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"⏰ <b>Время начала:</b> {self.format_msk_time(current_time)}\n\n"
                f"🏁 <b>Фаза пряток началась!</b>\n\n"
            )
            
            # Уведомляем водителей
            drivers_text = start_text + (
                f"🚗 <b>Ваша роль: Водитель</b>\n\n"
                f"У вас есть {self.hiding_time} минут на то, чтобы спрятаться!\n"
                f"📸 <b>ОБЯЗАТЕЛЬНО отправьте фото места пряток в бот!</b>\n"
                f"📍 Можете также отправить геолокацию.\n\n"
                f"⚠️ За {self.hiding_warning_time} минут до конца получите предупреждение."
            )
            
            # Уведомляем искателей
            seekers_text = start_text + (
                f"🔍 <b>Ваша роль: Искатель</b>\n\n"
                f"Водители прячутся {self.hiding_time} минут.\n"
                f"⏰ Фаза поиска начнется в {self.format_msk_time(current_time + timedelta(minutes=self.hiding_time))}\n\n"
                f"🚧 <b>Пожалуйста, не подглядывайте за водителями!</b>\n"
                f"Для честной игры не следите за водителями во время пряток."
            )
            
            # Отправляем уведомления участникам
            sent_count = 0
            for participant in game.participants:
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        if participant.role == GameRole.DRIVER:
                            text = drivers_text
                        else:
                            text = seekers_text
                        
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=text,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка уведомления о старте пользователю {user.telegram_id}: {e}")
            
            # Уведомляем админов
            admins = UserService.get_admin_users()
            for admin in admins:
                try:
                    admin_text = (
                        f"👨‍💼 <b>Админ-уведомление: Игра началась!</b>\n\n"
                        f"🎮 <b>Игра:</b> {game.district} (ID: {game.id})\n"
                        f"⏰ <b>Время:</b> {self.format_msk_time(current_time)}\n"
                        f"👥 <b>Участников:</b> {len(game.participants)}\n"
                        f"🚗 <b>Водителей:</b> {sum(1 for p in game.participants if p.role == GameRole.DRIVER)}\n\n"
                        f"📊 Отправлено уведомлений: {sent_count}"
                    )
                    
                    await self.bot.send_message(
                        chat_id=admin.telegram_id,
                        text=admin_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка уведомления админа {admin.telegram_id}: {e}")
            
            logger.info(f"Отправлены уведомления о начале игры для игры {game_id} ({sent_count} участников)")
            
        except Exception as e:
            logger.error(f"Ошибка уведомления о начале игры {game_id}: {e}")
    
    async def notify_game_cancelled(self, game_id: int, reason: str):
        """Уведомление об отмене игры"""
        try:
            game = GameService.get_game_by_id(game_id)
            if not game:
                return
            
            cancel_text = (
                f"❌ <b>Игра отменена</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"⏰ <b>Время:</b> {game.scheduled_at.strftime('%d.%m.%Y в %H:%M')}\n\n"
                f"<b>Причина:</b> {reason}\n\n"
                f"Извините за неудобства. Следите за новыми играми!"
            )
            
            sent_count = 0
            for participant in game.participants:
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=cancel_text,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка уведомления об отмене игры пользователю {user.telegram_id}: {e}")
            
            logger.info(f"Отправлены уведомления об отмене игры {game_id} ({sent_count} участников)")
            
        except Exception as e:
            logger.error(f"Ошибка уведомления об отмене игры {game_id}: {e}")
    
    async def notify_searching_phase_started(self, game_id: int):
        """Уведомление о начале фазы поиска"""
        try:
            game = GameService.get_game_by_id(game_id)
            if not game:
                return
            
            # Проверяем, все ли водители спрятались
            hiding_stats = GameService.get_hiding_stats(game_id)
            all_hidden = hiding_stats.get('all_hidden', False)
            
            current_time = datetime.now(DEFAULT_TIMEZONE)
            
            # Формируем текст уведомления
            if all_hidden:
                phase_text = (
                    f"🔍 <b>Фаза поиска началась!</b>\n\n"
                    f"🎮 <b>Игра:</b> {game.district}\n"
                    f"⏰ <b>Время:</b> {self.format_msk_time(current_time)}\n\n"
                    f"✅ <b>Все водители спрятались!</b>\n"
                    f"🚗 Водителей: {hiding_stats['total_drivers']}\n\n"
                )
            else:
                not_hidden_count = hiding_stats.get('not_hidden_count', 0)
                phase_text = (
                    f"🔍 <b>Фаза поиска началась!</b>\n\n"
                    f"🎮 <b>Игра:</b> {game.district}\n"
                    f"⏰ <b>Время:</b> {self.format_msk_time(current_time)}\n\n"
                    f"⚠️ <b>Внимание!</b> {not_hidden_count} водителей не успели спрятаться.\n\n"
                )
            
            # Разные тексты для водителей и искателей
            drivers_text = phase_text + (
                f"🚗 <b>Инструкции для водителей:</b>\n"
                f"• Оставайтесь в своем месте пряток\n"
                f"• Подтверждайте находку кнопкой 'Меня нашли'\n"
                f"• Можете отправлять дополнительные фото\n\n"
                f"Удачной игры! Пусть вас не найдут 😉"
            )
            
            seekers_text = phase_text + (
                f"🔍 <b>Инструкции для искателей:</b>\n"
                f"• Ищите спрятанные машины\n"
                f"• Отправляйте фото найденных машин\n"
                f"• Используйте кнопку 'Я нашел водителя'\n"
                f"• Координируйтесь с другими искателями\n\n"
                f"Удачной охоты! 🕵️‍♂️"
            )
            
            # Отправляем уведомления участникам
            sent_count = 0
            for participant in game.participants:
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        if participant.role == GameRole.DRIVER:
                            text = drivers_text
                        else:
                            text = seekers_text
                        
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=text,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка уведомления о начале поиска пользователю {user.telegram_id}: {e}")
            
            # Уведомляем админов
            admins = UserService.get_admin_users()
            for admin in admins:
                try:
                    admin_text = (
                        f"👨‍💼 <b>Админ-уведомление: Началась фаза поиска</b>\n\n"
                        f"🎮 <b>Игра:</b> {game.district} (ID: {game.id})\n"
                        f"⏰ <b>Время:</b> {self.format_msk_time(current_time)}\n"
                        f"🚗 <b>Водителей:</b> {hiding_stats['total_drivers']}\n"
                        f"✅ <b>Спрятались:</b> {hiding_stats['hidden_count']}\n"
                        f"❌ <b>Не спрятались:</b> {hiding_stats['not_hidden_count']}\n\n"
                        f"📊 Отправлено уведомлений: {sent_count}"
                    )
                    
                    await self.bot.send_message(
                        chat_id=admin.telegram_id,
                        text=admin_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка уведомления админа {admin.telegram_id} о начале поиска: {e}")
            
            logger.info(f"Отправлены уведомления о начале фазы поиска для игры {game_id} ({sent_count} участников)")
            
        except Exception as e:
            logger.error(f"Ошибка уведомления о начале фазы поиска для игры {game_id}: {e}")
    
    async def notify_game_ended(self, game_id: int, reason: str):
        """Уведомление о завершении игры"""
        try:
            game = GameService.get_game_by_id(game_id)
            if not game:
                return
            
            current_time = datetime.now(DEFAULT_TIMEZONE)
            
            end_text = (
                f"🏁 <b>Игра завершена!</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"⏰ <b>Время завершения:</b> {self.format_msk_time(current_time)}\n\n"
                f"<b>Причина:</b> {reason}\n\n"
                f"Спасибо за участие! Ждем вас в новых играх!"
            )
            
            sent_count = 0
            for participant in game.participants:
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=end_text,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка уведомления о завершении игры пользователю {user.telegram_id}: {e}")
            
            logger.info(f"Отправлены уведомления о завершении игры {game_id} ({sent_count} участников)")
            
        except Exception as e:
            logger.error(f"Ошибка уведомления о завершении игры {game_id}: {e}")


# Глобальный экземпляр планировщика
enhanced_scheduler_service: Optional[EnhancedSchedulerService] = None


def get_enhanced_scheduler() -> Optional[EnhancedSchedulerService]:
    """Получение экземпляра улучшенного планировщика"""
    return enhanced_scheduler_service


def init_enhanced_scheduler(application: Application) -> EnhancedSchedulerService:
    """Инициализация улучшенного планировщика"""
    global enhanced_scheduler_service
    enhanced_scheduler_service = EnhancedSchedulerService(application)
    return enhanced_scheduler_service 