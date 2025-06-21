from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import selectinload
import logging
from src.models.base import get_db
from src.models.user import User
from src.models.game import Game, GameStatus, GameParticipant, GameRole
from src.services.user_service import UserService

logger = logging.getLogger(__name__)

class UserGameContext:
    """Класс для хранения контекста игрока"""
    
    def __init__(self, status: str, game: Optional[Game] = None, participant: Optional[GameParticipant] = None):
        self.status = status
        self.game = game
        self.participant = participant
        
    def __str__(self):
        return f"UserGameContext(status={self.status}, game_id={self.game.id if self.game else None})"

class UserContextService:
    """Сервис для определения контекста пользователя и формирования клавиатур"""
    
    # Возможные статусы пользователя
    STATUS_NORMAL = "normal"              # Обычный режим, нет активных игр
    STATUS_REGISTERED = "registered"      # Записан на предстоящую игру
    STATUS_IN_GAME = "in_game"           # Участвует в активной игре
    STATUS_GAME_FINISHED = "game_finished"  # Игра недавно завершена
    
    @staticmethod
    def get_user_game_context(user_id: int) -> UserGameContext:
        """Определить текущий игровой контекст пользователя"""
        db_generator = get_db()
        db = next(db_generator)
        if not isinstance(user_id, int):
            logger.error(f"Некорректный тип user_id: {user_id} (тип {type(user_id)})")
            return UserGameContext(UserContextService.STATUS_NORMAL)
        try:
            # Получаем пользователя
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                logger.warning(f"Пользователь с telegram_id {user_id} не найден")
                return UserGameContext(UserContextService.STATUS_NORMAL)
            
            # Находим все участия пользователя с релевантными статусами
            all_participations = db.query(GameParticipant)\
                .join(Game)\
                .options(selectinload(GameParticipant.game).selectinload(Game.participants))\
                .filter(
                    GameParticipant.user_id == user.id,
                    Game.status.in_([
                        GameStatus.RECRUITING,
                        GameStatus.UPCOMING, 
                        GameStatus.HIDING_PHASE,
                        GameStatus.SEARCHING_PHASE,
                        GameStatus.COMPLETED
                    ])
                )\
                .order_by(Game.scheduled_at.desc())\
                .all()
            
            if not all_participations:
                return UserGameContext(UserContextService.STATUS_NORMAL)
            
            # Разделяем участия по приоритету статусов
            active_games = []        # HIDING_PHASE, SEARCHING_PHASE
            upcoming_games = []      # RECRUITING, UPCOMING  
            completed_games = []     # COMPLETED
            
            for participation in all_participations:
                game = participation.game
                if game.status in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
                    active_games.append(participation)
                elif game.status in [GameStatus.RECRUITING, GameStatus.UPCOMING]:
                    upcoming_games.append(participation)
                elif game.status == GameStatus.COMPLETED:
                    completed_games.append(participation)
            
            # Проверяем по приоритету
            
            # 1. Активные игры (наивысший приоритет)
            if active_games:
                # Берем самую последнюю по времени планирования среди активных
                latest_active = max(active_games, key=lambda p: p.game.scheduled_at)
                return UserGameContext(
                    UserContextService.STATUS_IN_GAME,
                    latest_active.game,
                    latest_active
                )
            
            # 2. Предстоящие игры
            if upcoming_games:
                # Берем самую ближайшую предстоящую игру
                nearest_upcoming = min(upcoming_games, key=lambda p: p.game.scheduled_at)
                return UserGameContext(
                    UserContextService.STATUS_REGISTERED,
                    nearest_upcoming.game,
                    nearest_upcoming
                )
            
            # 3. Недавно завершенные игры
            if completed_games:
                # Берем самую последнюю завершенную
                latest_completed = max(completed_games, key=lambda p: p.game.scheduled_at)
                game = latest_completed.game
                
                # Проверяем, завершена ли игра недавно (в последние 5 минут)
                if game.ended_at and \
                   (datetime.now() - game.ended_at).total_seconds() < 60*5:
                    return UserGameContext(
                        UserContextService.STATUS_GAME_FINISHED,
                        game,
                        latest_completed
                    )
            
            return UserGameContext(UserContextService.STATUS_NORMAL)
            
        except Exception as e:
            logger.error(f"Ошибка при определении контекста пользователя {user_id}: {e}")
            return UserGameContext(UserContextService.STATUS_NORMAL)
    
    @staticmethod
    def get_user_current_game(user_id: int) -> Optional[Game]:
        """Получить текущую активную игру пользователя"""
        context = UserContextService.get_user_game_context(user_id)
        return context.game if context.status in [
            UserContextService.STATUS_REGISTERED,
            UserContextService.STATUS_IN_GAME,
            UserContextService.STATUS_GAME_FINISHED
        ] else None

    @staticmethod
    def is_user_in_active_game(user_id: int) -> bool:
        """Проверить, участвует ли пользователь в активной игре"""
        context = UserContextService.get_user_game_context(user_id)
        return context.status == UserContextService.STATUS_IN_GAME
    
    @staticmethod
    def get_user_active_game(user_id: int) -> Optional[Game]:
        """Получить игру, в которой пользователь сейчас играет (только активные игры)"""
        context = UserContextService.get_user_game_context(user_id)
        return context.game if context.status == UserContextService.STATUS_IN_GAME else None
    
    @staticmethod
    def get_user_upcoming_games(user_id: int) -> list[Game]:
        """Получить все предстоящие игры пользователя"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                return []
                
            upcoming_participations = db.query(GameParticipant)\
                .join(Game)\
                .options(selectinload(GameParticipant.game))\
                .filter(
                    GameParticipant.user_id == user.id,
                    Game.status.in_([GameStatus.RECRUITING, GameStatus.UPCOMING])
                )\
                .order_by(Game.scheduled_at.asc())\
                .all()
            
            return [participation.game for participation in upcoming_participations]
            
        except Exception as e:
            logger.error(f"Ошибка при получении предстоящих игр пользователя {user_id}: {e}")
            return []

    @staticmethod
    def get_user_role_in_game(user_id: int, game_id: int) -> Optional[GameRole]:
        """Получить роль пользователя в конкретной игре"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                return None
                
            participant = db.query(GameParticipant)\
                .filter(
                    GameParticipant.user_id == user.id,
                    GameParticipant.game_id == game_id
                )\
                .first()
            
            return participant.role if participant else None
            
        except Exception as e:
            logger.error(f"Ошибка при получении роли пользователя {user_id} в игре {game_id}: {e}")
            return None
    
    @staticmethod
    def get_context_info(user_id: int) -> Dict[str, Any]:
        """Получить полную информацию о контексте пользователя"""
        context = UserContextService.get_user_game_context(user_id)
        is_admin = UserService.is_admin(user_id)
        
        info = {
            "status": context.status,
            "is_admin": is_admin,
            "current_game": None,
            "participant": None,
            "role": None,
            "upcoming_games": [],
            "total_upcoming_games": 0
        }
        
        # Информация о текущей игре (активной, зарегистрированной или недавно завершенной)
        if context.game:
            info["current_game"] = {
                "id": context.game.id,
                "district": context.game.district,
                "status": context.game.status,
                "scheduled_at": context.game.scheduled_at,
                "started_at": context.game.started_at,
                "ended_at": context.game.ended_at,
                "max_participants": context.game.max_participants,
                "max_drivers": context.game.max_drivers,
                "has_zone": context.game.has_game_zone
            }
            
        if context.participant:
            info["participant"] = {
                "role": context.participant.role,
                "joined_at": context.participant.joined_at,
                "is_ready": context.participant.is_ready,
                "is_found": context.participant.is_found,
                "has_hidden": context.participant.has_hidden
            }
            info["role"] = context.participant.role
        
        # Получаем информацию обо всех предстоящих играх
        upcoming_games = UserContextService.get_user_upcoming_games(user_id)
        info["upcoming_games"] = [
            {
                "id": game.id,
                "district": game.district,
                "status": game.status,
                "scheduled_at": game.scheduled_at,
                "max_participants": game.max_participants
            }
            for game in upcoming_games
        ]
        info["total_upcoming_games"] = len(upcoming_games)
        
        return info 