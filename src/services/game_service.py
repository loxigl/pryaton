from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
from datetime import datetime
import random
from loguru import logger

from src.models.base import get_db
from src.models.game import Game, GameStatus, GameParticipant, GameRole
from src.models.user import User

class GameService:
    """Сервис для работы с играми"""
    
    @staticmethod
    def create_game(
        district: str,
        max_participants: int,
        scheduled_at: datetime,
        creator_id: int,
        max_drivers: int = 1,
        description: Optional[str] = None
    ) -> Game:
        """Создание новой игры"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Проверяем корректность количества водителей
        if max_drivers >= max_participants:
            raise ValueError("Количество водителей не может быть больше или равно общему количеству участников")
        
        game = Game(
            district=district,
            max_participants=max_participants,
            max_drivers=max_drivers,
            scheduled_at=scheduled_at,
            creator_id=creator_id,
            status=GameStatus.RECRUITING,
            description=description
        )
        
        db.add(game)
        db.commit()
        db.refresh(game)
        
        # Планируем уведомления для новой игры
        from src.services.enhanced_scheduler_service import get_enhanced_scheduler
        scheduler = get_enhanced_scheduler()
        if scheduler:
            scheduler.schedule_game_reminders(game.id)
        
        return game
    
    @staticmethod
    def update_game(
        game_id: int,
        district: Optional[str] = None,
        max_participants: Optional[int] = None,
        max_drivers: Optional[int] = None,
        scheduled_at: Optional[datetime] = None,
        description: Optional[str] = None
    ) -> bool:
        """Обновление данных игры (только до начала)"""
        db_generator = get_db()
        db = next(db_generator)
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.error(f"Игра с ID {game_id} не найдена")
            return False
        
        # Проверяем, что игра еще не началась
        if game.status not in [GameStatus.RECRUITING, GameStatus.UPCOMING]:
            logger.error(f"Игра с ID {game_id} уже началась или завершена, редактирование невозможно")
            return False
        
        # Обновляем поля
        if district is not None:
            game.district = district
        if scheduled_at is not None:
            game.scheduled_at = scheduled_at
        if description is not None:
            game.description = description
        
        # Особая обработка для max_participants и max_drivers
        current_participants = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
        
        if max_participants is not None:
            if max_participants < current_participants:
                logger.error(f"Нельзя уменьшить количество участников ниже текущего ({current_participants})")
                return False
            if max_drivers is not None and max_drivers >= max_participants:
                logger.error("Количество водителей не может быть больше или равно общему количеству участников")
                return False
            game.max_participants = max_participants
        
        if max_drivers is not None:
            max_parts = max_participants if max_participants is not None else game.max_participants
            if max_drivers >= max_parts:
                logger.error("Количество водителей не может быть больше или равно общему количеству участников")
                return False
            game.max_drivers = max_drivers
        
        db.commit()
        
        # Если изменилось время игры, перепланируем уведомления
        if scheduled_at is not None:
            from src.services.enhanced_scheduler_service import get_enhanced_scheduler
            scheduler = get_enhanced_scheduler()
            if scheduler:
                scheduler.cancel_game_jobs(game_id)
                scheduler.schedule_game_reminders(game_id)
        
        return True
    
    @staticmethod
    def get_game_by_id(game_id: int) -> Optional[Game]:
        """Получение игры по ID"""
        db_generator = get_db()
        db = next(db_generator)
        return db.query(Game).filter(Game.id == game_id).first()
    
    @staticmethod
    def get_upcoming_games(limit: int = 10) -> List[Game]:
        """Получение списка предстоящих игр"""
        db_generator = get_db()
        db = next(db_generator)
        return db.query(Game).filter(
            Game.status.in_([GameStatus.RECRUITING, GameStatus.UPCOMING]),
            Game.scheduled_at > datetime.now()
        ).order_by(Game.scheduled_at).limit(limit).all()
    
    @staticmethod
    def get_user_games(user_id: int) -> List[Game]:
        """Получение списка игр пользователя"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Подзапрос для получения ID игр, в которых участвует пользователь
        game_ids = db.query(GameParticipant.game_id).filter(GameParticipant.user_id == user_id).all()
        game_ids = [g[0] for g in game_ids]
        
        return db.query(Game).filter(Game.id.in_(game_ids)).order_by(Game.scheduled_at).all()
    
    @staticmethod
    def get_user_active_games(user_id: int) -> List[Game]:
        """Получение списка активных игр пользователя"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Подзапрос для получения ID игр, в которых участвует пользователь
        game_ids = db.query(GameParticipant.game_id).filter(GameParticipant.user_id == user_id).all()
        game_ids = [g[0] for g in game_ids]
        
        return db.query(Game).filter(
            Game.id.in_(game_ids),
            Game.status.in_([GameStatus.UPCOMING, GameStatus.IN_PROGRESS])
        ).order_by(Game.scheduled_at).all()
    
    @staticmethod
    def join_game(game_id: int, user_id: int) -> Optional[GameParticipant]:
        """Запись пользователя на игру"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Проверка существования игры
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.error(f"Игра с ID {game_id} не найдена")
            return None
        
        # Проверка статуса игры
        if game.status != GameStatus.RECRUITING:
            logger.error(f"Игра с ID {game_id} не доступна для записи, текущий статус: {game.status}")
            return None
        
        # Проверка наличия свободных мест
        participants_count = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
        if participants_count >= game.max_participants:
            logger.error(f"Игра с ID {game_id} уже заполнена")
            return None
        
        # Проверка, что пользователь еще не записан
        existing = db.query(GameParticipant).filter(
            GameParticipant.game_id == game_id,
            GameParticipant.user_id == user_id
        ).first()
        
        if existing:
            logger.error(f"Пользователь с ID {user_id} уже записан на игру с ID {game_id}")
            return existing
        
        # Создание записи об участнике
        participant = GameParticipant(
            game_id=game_id,
            user_id=user_id
        )
        
        db.add(participant)
        db.commit()
        db.refresh(participant)
        
        # Проверка, достигнуто ли максимальное количество участников
        new_count = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
        if new_count >= game.max_participants:
            # Меняем статус игры
            game.status = GameStatus.UPCOMING
            db.commit()
        
        return participant
    
    @staticmethod
    def leave_game(game_id: int, user_id: int) -> bool:
        """Отмена записи пользователя на игру"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Проверка существования записи
        participant = db.query(GameParticipant).filter(
            GameParticipant.game_id == game_id,
            GameParticipant.user_id == user_id
        ).first()
        
        if not participant:
            logger.error(f"Пользователь с ID {user_id} не записан на игру с ID {game_id}")
            return False
        
        # Удаление записи
        db.delete(participant)
        db.commit()
        
        # Обновление статуса игры, если он был UPCOMING
        game = db.query(Game).filter(Game.id == game_id).first()
        if game and game.status == GameStatus.UPCOMING:
            participants_count = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
            if participants_count < game.max_participants:
                game.status = GameStatus.RECRUITING
                db.commit()
        
        return True
    
    @staticmethod
    def assign_roles(game_id: int) -> List[Tuple[int, GameRole]]:
        """Распределение ролей между участниками игры с учетом количества водителей"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Получение игры и участников
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.error(f"Игра с ID {game_id} не найдена")
            return []
        
        participants = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).all()
        
        if not participants:
            logger.error(f"Игра с ID {game_id} не имеет участников")
            return []
        
        if len(participants) < 2:
            logger.error(f"Недостаточно участников для распределения ролей")
            return []
        
        # Проверяем, что количество водителей не превышает количество участников
        max_drivers = min(game.max_drivers, len(participants) - 1)  # Минимум 1 искатель
        
        # Рандомный выбор водителей
        driver_indices = random.sample(range(len(participants)), max_drivers)
        
        # Распределение ролей
        result = []
        for i, participant in enumerate(participants):
            if i in driver_indices:
                participant.role = GameRole.DRIVER
            else:
                participant.role = GameRole.SEEKER
            
            result.append((participant.user_id, participant.role))
        
        db.commit()
        
        logger.info(f"Роли распределены для игры {game_id}: {max_drivers} водителей, {len(participants) - max_drivers} искателей")
        return result
    
    @staticmethod
    def _start_game_internal(game_id: int) -> bool:
        """Внутренний метод запуска игры без уведомлений"""
        db_generator = get_db()
        db = next(db_generator)
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.error(f"Игра с ID {game_id} не найдена")
            return False
        
        # Проверка, что все роли назначены
        participants = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).all()
        for participant in participants:
            if not participant.role:
                logger.error(f"Не все роли назначены для игры с ID {game_id}")
                return False
        
        # Обновление статуса игры
        game.status = GameStatus.IN_PROGRESS
        game.started_at = datetime.now()
        db.commit()
        
        logger.info(f"Игра {game_id} запущена (внутренний вызов)")
        return True
    
    @staticmethod
    def start_game(game_id: int, start_type: str = "manual") -> bool:
        """Начало игры с поддержкой уведомлений"""
        # Запускаем игру
        if not GameService._start_game_internal(game_id):
            return False
        
        # Отправляем уведомления через планировщик
        from src.services.enhanced_scheduler_service import get_enhanced_scheduler
        scheduler = get_enhanced_scheduler()
        if scheduler:
            import asyncio
            # Запускаем асинхронное уведомление
            asyncio.create_task(scheduler.notify_game_started(game_id, start_type))
            
            # Отменяем все оставшиеся задачи для этой игры
            scheduler.cancel_game_jobs(game_id)
        
        logger.info(f"Игра {game_id} запущена ({start_type})")
        return True
    
    @staticmethod
    def end_game(game_id: int) -> bool:
        """Завершение игры"""
        db_generator = get_db()
        db = next(db_generator)
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.error(f"Игра с ID {game_id} не найдена")
            return False
        
        # Обновление статуса игры
        game.status = GameStatus.COMPLETED
        game.ended_at = datetime.now()
        db.commit()
        
        return True
    
    @staticmethod
    def cancel_game(game_id: int, reason: str = "Игра отменена администратором") -> bool:
        """Отмена игры с поддержкой уведомлений"""
        db_generator = get_db()
        db = next(db_generator)
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.error(f"Игра с ID {game_id} не найдена")
            return False
        
        # Обновление статуса игры
        game.status = GameStatus.CANCELED
        db.commit()
        
        # Отменяем все запланированные задачи для игры и отправляем уведомления
        from src.services.enhanced_scheduler_service import get_enhanced_scheduler
        scheduler = get_enhanced_scheduler()
        if scheduler:
            scheduler.cancel_game_jobs(game_id)
            
            import asyncio
            # Запускаем асинхронное уведомление об отмене
            asyncio.create_task(scheduler.notify_game_cancelled(game_id, reason))
        
        logger.info(f"Игра {game_id} отменена: {reason}")
        return True
    
    @staticmethod
    def can_edit_game(game_id: int) -> bool:
        """Проверка возможности редактирования игры"""
        db_generator = get_db()
        db = next(db_generator)
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return False
        
        return game.status in [GameStatus.RECRUITING, GameStatus.UPCOMING]
    
    @staticmethod
    def mark_participant_found(game_id: int, user_id: int) -> bool:
        """Отметка участника как найденного"""
        db_generator = get_db()
        db = next(db_generator)
        
        participant = db.query(GameParticipant).filter(
            GameParticipant.game_id == game_id,
            GameParticipant.user_id == user_id
        ).first()
        
        if not participant:
            logger.error(f"Участник с ID {user_id} не найден в игре с ID {game_id}")
            return False
        
        participant.is_found = True
        participant.found_at = datetime.now()
        db.commit()
        
        return True 