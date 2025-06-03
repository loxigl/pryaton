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
from src.services.user_service import UserService
from src.services.game_service import GameService


class SchedulerService:
    """Сервис для управления планировщиком задач и уведомлениями"""
    
    def __init__(self, application: Application):
        self.scheduler = AsyncIOScheduler()
        self.application = application
        self.bot = application.bot
        
        # Настройки из переменных окружения
        self.hiding_time = int(os.getenv("HIDING_TIME", 30))  # минуты
        self.reminder_times = [int(x) for x in os.getenv("REMINDER_BEFORE_GAME", "60,24,5").split(",")]  # минуты
        
    def start(self):
        """Запуск планировщика"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Планировщик задач запущен")
    
    def shutdown(self):
        """Остановка планировщика"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик задач остановлен")
    
    def schedule_game_reminders(self, game_id: int):
        """Планирование напоминаний для игры"""
        game = GameService.get_game_by_id(game_id)
        if not game:
            logger.error(f"Игра {game_id} не найдена при планировании напоминаний")
            return
        
        # Планируем напоминания
        for reminder_minutes in self.reminder_times:
            reminder_time = game.scheduled_at - timedelta(minutes=reminder_minutes)
            
            # Проверяем, что время напоминания еще не прошло
            if reminder_time > datetime.now():
                job_id = f"reminder_{game_id}_{reminder_minutes}min"
                
                self.scheduler.add_job(
                    self.send_game_reminder,
                    trigger=DateTrigger(run_date=reminder_time),
                    args=[game_id, reminder_minutes],
                    id=job_id,
                    replace_existing=True
                )
                
                logger.info(f"Запланировано напоминание для игры {game_id} за {reminder_minutes} минут: {reminder_time}")
        
        # Планируем начало игры
        start_job_id = f"start_game_{game_id}"
        self.scheduler.add_job(
            self.start_game,
            trigger=DateTrigger(run_date=game.scheduled_at),
            args=[game_id],
            id=start_job_id,
            replace_existing=True
        )
        
        logger.info(f"Запланирован автоматический старт игры {game_id}: {game.scheduled_at}")
        
        # Планируем таймер прятки после начала игры
        hiding_end_time = game.scheduled_at + timedelta(minutes=self.hiding_time)
        hiding_job_id = f"hiding_end_{game_id}"
        
        self.scheduler.add_job(
            self.end_hiding_phase,
            trigger=DateTrigger(run_date=hiding_end_time),
            args=[game_id],
            id=hiding_job_id,
            replace_existing=True
        )
        
        logger.info(f"Запланировано окончание пряток для игры {game_id}: {hiding_end_time}")
    
    def cancel_game_jobs(self, game_id: int):
        """Отмена всех задач для игры"""
        jobs_to_remove = []
        
        for job in self.scheduler.get_jobs():
            if str(game_id) in job.id:
                jobs_to_remove.append(job.id)
        
        for job_id in jobs_to_remove:
            self.scheduler.remove_job(job_id)
            logger.info(f"Отменена задача {job_id} для игры {game_id}")
    
    async def send_game_reminder(self, game_id: int, minutes_before: int):
        """Отправка напоминания о предстоящей игре"""
        try:
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
            for participant in game.participants:
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=reminder_text,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки напоминания пользователю {user.telegram_id}: {e}")
            
            logger.info(f"Отправлены напоминания для игры {game_id} ({len(game.participants)} участников)")
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминаний для игры {game_id}: {e}")
    
    async def start_game(self, game_id: int):
        """Автоматический запуск игры"""
        try:
            game = GameService.get_game_by_id(game_id)
            if not game:
                logger.error(f"Игра {game_id} не найдена при автоматическом запуске")
                return
            
            if game.status != GameStatus.UPCOMING:
                logger.info(f"Игра {game_id} имеет статус {game.status}, пропускаем автозапуск")
                return
            
            # Проверяем количество участников
            if len(game.participants) < 2:
                # Недостаточно участников - отменяем игру
                GameService.cancel_game(game_id)
                await self.notify_game_cancelled(game_id, "Недостаточно участников")
                return
            
            # Распределяем роли
            GameService.assign_roles(game_id)
            
            # Запускаем игру
            if GameService.start_game(game_id):
                await self.notify_game_started(game_id)
                logger.info(f"Игра {game_id} автоматически запущена")
            else:
                logger.error(f"Ошибка автоматического запуска игры {game_id}")
                
        except Exception as e:
            logger.error(f"Ошибка автоматического запуска игры {game_id}: {e}")
    
    async def end_hiding_phase(self, game_id: int):
        """Завершение фазы прятки"""
        try:
            game = GameService.get_game_by_id(game_id)
            if not game or game.status not in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
                logger.info(f"Игра {game_id} не активна, пропускаем завершение прятки")
                return
            
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
                f"Отправляйте фотографии найденных машин в бот для подтверждения."
            )
            
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
                    except Exception as e:
                        logger.error(f"Ошибка уведомления об окончании прятки пользователю {user.telegram_id}: {e}")
            
            logger.info(f"Завершена фаза прятки для игры {game_id}")
            
        except Exception as e:
            logger.error(f"Ошибка завершения фазы прятки для игры {game_id}: {e}")
    
    async def notify_game_started(self, game_id: int):
        """Уведомление о начале игры"""
        try:
            game = GameService.get_game_by_id(game_id)
            if not game:
                return
            
            start_text = (
                f"🚀 <b>Игра началась!</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n"
                f"⏰ <b>Время начала:</b> {datetime.now().strftime('%H:%M')}\n\n"
            )
            
            # Уведомляем водителей
            drivers_text = start_text + (
                f"🚗 <b>Ваша роль: Водитель</b>\n\n"
                f"У вас есть {self.hiding_time} минут на то, чтобы спрятаться!\n"
                f"📍 Отправьте геолокацию когда будете готовы.\n"
                f"📸 Можете отправить фото места пряток для администрации."
            )
            
            # Уведомляем искателей
            seekers_text = start_text + (
                f"🔍 <b>Ваша роль: Искатель</b>\n\n"
                f"Водители прячутся {self.hiding_time} минут.\n"
                f"📍 Отправляйте геолокацию для отслеживания.\n"
                f"⏰ Поиск начнется через {self.hiding_time} минут!"
            )
            
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
                    except Exception as e:
                        logger.error(f"Ошибка уведомления о начале игры пользователю {user.telegram_id}: {e}")
            
            logger.info(f"Отправлены уведомления о начале игры {game_id}")
            
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
            
            for participant in game.participants:
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        await self.bot.send_message(
                            chat_id=user.telegram_id,
                            text=cancel_text,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка уведомления об отмене игры пользователю {user.telegram_id}: {e}")
            
            logger.info(f"Отправлены уведомления об отмене игры {game_id}")
            
        except Exception as e:
            logger.error(f"Ошибка уведомления об отмене игры {game_id}: {e}")


# Глобальный экземпляр планировщика
scheduler_service: Optional[SchedulerService] = None


def get_scheduler() -> Optional[SchedulerService]:
    """Получение экземпляра планировщика"""
    return scheduler_service


def init_scheduler(application: Application) -> SchedulerService:
    """Инициализация планировщика"""
    global scheduler_service
    scheduler_service = SchedulerService(application)
    return scheduler_service 