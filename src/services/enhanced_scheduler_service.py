import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from telegram.ext import Application

from src.models.base import get_db
from src.models.game import Game, GameStatus, GameParticipant, GameRole
from src.models.scheduled_event import ScheduledEvent, EventType
from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.event_persistence_service import EventPersistenceService


class EnhancedSchedulerService:
    """Улучшенный сервис планировщика с персистентными событиями"""
    
    def __init__(self, application: Application):
        self.scheduler = AsyncIOScheduler()
        self.application = application
        self.bot = application.bot
        
        # Настройки из переменных окружения
        self.hiding_time = int(os.getenv("HIDING_TIME", 30))  # минуты
        self.reminder_times = [int(x) for x in os.getenv("REMINDER_BEFORE_GAME", "60,24,5").split(",")]  # минуты
        
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
        """Восстановление всех невыполненных событий из БД"""
        try:
            pending_events = EventPersistenceService.get_pending_events()
            restored_count = 0
            
            for event in pending_events:
                # Проверяем, что событие еще актуально
                if event.scheduled_at > datetime.now():
                    success = self._schedule_event_from_db(event)
                    if success:
                        restored_count += 1
                else:
                    # Событие просрочено - отмечаем как выполненное
                    EventPersistenceService.mark_event_executed(event.id)
                    logger.warning(f"Просроченное событие отмечено как выполненное: {event}")
            
            logger.info(f"Восстановлено {restored_count} событий из БД")
            
        except Exception as e:
            logger.error(f"Ошибка восстановления событий из БД: {e}")
    
    def _schedule_event_from_db(self, event: ScheduledEvent) -> bool:
        """Планирование события из БД"""
        try:
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
            elif event.event_type == "search_phase_end":
                func = self.end_search_phase
                args = [event.game_id, event.id]
            elif event.event_type == "game_cleanup":
                func = self.cleanup_game
                args = [event.game_id, event.id]
            else:
                logger.warning(f"Неизвестный тип события: {event.event_type}")
                return False
            
            # Планируем событие
            self.scheduler.add_job(
                func,
                trigger=DateTrigger(run_date=event.scheduled_at),
                args=args,
                id=event.job_id,
                replace_existing=True
            )
            
            logger.debug(f"Восстановлено событие: {event}")
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
        
        # Планируем напоминания
        for reminder_minutes in self.reminder_times:
            reminder_time = game.scheduled_at - timedelta(minutes=reminder_minutes)
            
            # Проверяем, что время напоминания еще не прошло
            if reminder_time > datetime.now():
                # Определяем тип события
                if reminder_minutes >= 60:
                    event_type = f"reminder_{reminder_minutes // 60}hour"
                else:
                    event_type = f"reminder_{reminder_minutes}min"
                
                # Сохраняем в БД
                event = EventPersistenceService.save_event(
                    game_id=game_id,
                    event_type=event_type,
                    scheduled_at=reminder_time,
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
        
        # Планируем начало игры
        start_event = EventPersistenceService.save_event(
            game_id=game_id,
            event_type="game_start",
            scheduled_at=game.scheduled_at,
            event_data={}
        )
        
        if start_event:
            self.scheduler.add_job(
                self.start_game,
                trigger=DateTrigger(run_date=game.scheduled_at),
                args=[game_id, start_event.id],
                id=start_event.job_id,
                replace_existing=True
            )
            
            logger.info(f"Запланирован автоматический старт игры {game_id}: {game.scheduled_at}")
        
        # Планируем таймер прятки после начала игры
        hiding_end_time = game.scheduled_at + timedelta(minutes=self.hiding_time)
        hiding_event = EventPersistenceService.save_event(
            game_id=game_id,
            event_type="hiding_phase_end",
            scheduled_at=hiding_end_time,
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
            
            logger.info(f"Запланировано окончание прятки для игры {game_id}: {hiding_end_time}")
    
    def cancel_game_jobs(self, game_id: int):
        """Отмена всех задач для игры"""
        # Отменяем в БД
        cancelled_count = EventPersistenceService.cancel_game_events(game_id)
        
        # Отменяем в планировщике
        jobs_to_remove = []
        for job in self.scheduler.get_jobs():
            if str(game_id) in job.id:
                jobs_to_remove.append(job.id)
        
        for job_id in jobs_to_remove:
            try:
                self.scheduler.remove_job(job_id)
                logger.debug(f"Отменена задача планировщика {job_id}")
            except Exception as e:
                logger.warning(f"Ошибка отмены задачи {job_id}: {e}")
        
        logger.info(f"Отменено {cancelled_count} событий для игры {game_id}")
    
    async def send_game_reminder(self, game_id: int, minutes_before: int, event_id: int):
        """Отправка напоминания о предстоящей игре"""
        try:
            # Отмечаем событие как выполненное
            EventPersistenceService.mark_event_executed(event_id)
            
            game = GameService.get_game_by_id(game_id)
            if not game or game.status not in [GameStatus.RECRUITING, GameStatus.UPCOMING]:
                logger.info(f"Игра {game_id} отменена или уже началась, пропускаем напоминание")
                return
            
            # Формируем текст напоминания
            if minutes_before >= 60:
                time_text = f"{minutes_before // 60} час{'а' if minutes_before // 60 < 5 else 'ов'}"
            else:
                time_text = f"{minutes_before} минут"
            
            reminder_text = (
                f"⏰ <b>Напоминание о игре!</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"⏰ <b>Начало:</b> {game.scheduled_at.strftime('%d.%m.%Y в %H:%M')}\n"
                f"📍 <b>До начала:</b> {time_text}\n\n"
                f"Участников: {len(game.participants)}/{game.max_participants}\n\n"
                f"Не забудьте подготовиться к игре!"
            )
            
            # Отправляем напоминания всем участникам
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
            
            logger.info(f"Отправлены напоминания для игры {game_id} ({sent_count} участников)")
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминаний для игры {game_id}: {e}")
    
    async def start_game(self, game_id: int, event_id: int, start_type: str = "auto"):
        """Запуск игры с уведомлениями"""
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
            
            # Запускаем игру
            if GameService._start_game_internal(game_id):
                await self.notify_game_started(game_id, start_type)
                logger.info(f"Игра {game_id} запущена ({start_type})")
            else:
                logger.error(f"Ошибка запуска игры {game_id}")
                
        except Exception as e:
            logger.error(f"Ошибка запуска игры {game_id}: {e}")
    
    async def end_hiding_phase(self, game_id: int, event_id: int):
        """Завершение фазы прятки"""
        try:
            # Отмечаем событие как выполненное
            EventPersistenceService.mark_event_executed(event_id)
            
            game = GameService.get_game_by_id(game_id)
            if not game or game.status != GameStatus.IN_PROGRESS:
                logger.info(f"Игра {game_id} не активна, пропускаем завершение прятки")
                return
            
            hiding_end_text = (
                f"⏰ <b>Время прятки истекло!</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"🏁 <b>Фаза поиска началась!</b>\n\n"
            )
            
            # Уведомляем водителей
            drivers_text = hiding_end_text + (
                f"🚗 <b>Водители:</b> Время прятки закончилось!\n"
                f"Теперь вас могут искать. Удачи!"
            )
            
            # Уведомляем искателей
            seekers_text = hiding_end_text + (
                f"🔍 <b>Искатели:</b> Начинайте поиск!\n"
                f"Отправляйте фотографии найденных машин в бот для подтверждения."
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
                        logger.error(f"Ошибка уведомления об окончании прятки пользователю {user.telegram_id}: {e}")
            
            logger.info(f"Завершена фаза прятки для игры {game_id} ({sent_count} уведомлений)")
            
        except Exception as e:
            logger.error(f"Ошибка завершения фазы прятки для игры {game_id}: {e}")
    
    async def end_search_phase(self, game_id: int, event_id: int):
        """Завершение фазы поиска (автоматическое завершение игры)"""
        try:
            # Отмечаем событие как выполненное
            EventPersistenceService.mark_event_executed(event_id)
            
            game = GameService.get_game_by_id(game_id)
            if not game or game.status != GameStatus.IN_PROGRESS:
                logger.info(f"Игра {game_id} не активна, пропускаем завершение поиска")
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
        """Уведомление о начале игры с указанием типа запуска"""
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
            
            start_text += (
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"⏰ <b>Время начала:</b> {datetime.now().strftime('%H:%M')}\n\n"
            )
            
            # Уведомляем водителей
            drivers_text = start_text + (
                f"🚗 <b>Ваша роль: Водитель</b>\n\n"
                f"У вас есть {self.hiding_time} минут на то, чтобы спрятаться!\n"
                f"📍 Отправьте геолокацию когда будете готовы.\n"
                f"📸 Можете отправить фото места прятки для администрации."
            )
            
            # Уведомляем искателей
            seekers_text = start_text + (
                f"🔍 <b>Ваша роль: Искатель</b>\n\n"
                f"Водители прячутся {self.hiding_time} минут.\n"
                f"📍 Отправляйте геолокацию для отслеживания.\n"
                f"⏰ Поиск начнется через {self.hiding_time} минут!"
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
                        logger.error(f"Ошибка уведомления о начале игры пользователю {user.telegram_id}: {e}")
            
            logger.info(f"Отправлены уведомления о начале игры {game_id} ({sent_count} участников)")
            
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
    
    async def notify_game_ended(self, game_id: int, reason: str):
        """Уведомление о завершении игры"""
        try:
            game = GameService.get_game_by_id(game_id)
            if not game:
                return
            
            end_text = (
                f"🏁 <b>Игра завершена!</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"⏰ <b>Время завершения:</b> {datetime.now().strftime('%H:%M')}\n\n"
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
    
    def get_scheduled_events_info(self, game_id: Optional[int] = None) -> dict:
        """Получение информации о запланированных событиях"""
        try:
            if game_id:
                events = EventPersistenceService.get_game_events(game_id)
            else:
                events = EventPersistenceService.get_pending_events()
            
            events_by_game = {}
            for event in events:
                if event.game_id not in events_by_game:
                    events_by_game[event.game_id] = []
                events_by_game[event.game_id].append(event)
            
            stats = EventPersistenceService.get_events_statistics()
            
            return {
                "events_by_game": events_by_game,
                "statistics": stats,
                "scheduler_jobs": len(self.scheduler.get_jobs())
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о событиях: {e}")
            return {"events_by_game": {}, "statistics": {}, "scheduler_jobs": 0}


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