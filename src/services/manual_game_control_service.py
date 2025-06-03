from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger
from datetime import datetime

from src.models.base import get_db
from src.models.game import Game, GameParticipant, GameStatus, GameRole
from src.models.user import User
from src.services.game_settings_service import GameSettingsService
from src.services.game_service import GameService

class ManualGameControlService:
    """Сервис для ручного управления игрой администратором"""
    
    @staticmethod
    def manual_start_hiding_phase(game_id: int, admin_user_id: int) -> Dict[str, Any]:
        """Ручной запуск фазы пряток"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return {"success": False, "error": "Игра не найдена"}
            
            if game.status != GameStatus.UPCOMING:
                return {"success": False, "error": f"Игра в статусе {game.status.value}, нельзя начать фазу пряток"}
            
            # Проверяем, что роли распределены
            participants_with_roles = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.role.isnot(None)
            ).count()
            
            total_participants = len(game.participants)
            
            if participants_with_roles != total_participants:
                return {"success": False, "error": "Не все участники имеют назначенные роли"}
            
            # Запускаем фазу пряток
            game.status = GameStatus.HIDING_PHASE
            game.started_at = datetime.now()
            
            db.commit()
            
            logger.info(f"Админ {admin_user_id} вручную запустил фазу пряток для игры {game_id}")
            
            return {
                "success": True,
                "message": "Фаза пряток начата",
                "game_status": game.status.value,
                "started_at": game.started_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при ручном запуске фазы пряток: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    @staticmethod
    def manual_start_searching_phase(game_id: int, admin_user_id: int) -> Dict[str, Any]:
        """Ручной запуск фазы поиска"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return {"success": False, "error": "Игра не найдена"}
            
            if game.status != GameStatus.HIDING_PHASE:
                return {"success": False, "error": f"Игра в статусе {game.status.value}, нельзя начать фазу поиска"}
            
            # Запускаем фазу поиска
            game.status = GameStatus.SEARCHING_PHASE
            
            db.commit()
            
            logger.info(f"Админ {admin_user_id} вручную запустил фазу поиска для игры {game_id}")
            
            return {
                "success": True,
                "message": "Фаза поиска начата",
                "game_status": game.status.value
            }
            
        except Exception as e:
            logger.error(f"Ошибка при ручном запуске фазы поиска: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    @staticmethod
    def manual_end_game(game_id: int, admin_user_id: int, reason: str = "Завершено администратором") -> Dict[str, Any]:
        """Ручное завершение игры"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return {"success": False, "error": "Игра не найдена"}
            
            if game.status in [GameStatus.COMPLETED, GameStatus.CANCELED]:
                return {"success": False, "error": f"Игра уже завершена со статусом {game.status.value}"}
            
            # Завершаем игру
            game.status = GameStatus.COMPLETED
            game.ended_at = datetime.now()
            if reason:
                game.notes = f"{game.notes or ''}\nЗавершено админом: {reason}".strip()
            
            db.commit()
            
            logger.info(f"Админ {admin_user_id} вручную завершил игру {game_id} с причиной: {reason}")
            
            return {
                "success": True,
                "message": "Игра завершена",
                "game_status": game.status.value,
                "ended_at": game.ended_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при ручном завершении игры: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    @staticmethod
    def manual_mark_participant_found(game_id: int, participant_id: int, admin_user_id: int) -> Dict[str, Any]:
        """Ручная отметка участника как найденного"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            participant = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.id == participant_id
            ).first()
            
            if not participant:
                return {"success": False, "error": "Участник не найден"}
            
            if participant.role != GameRole.DRIVER:
                return {"success": False, "error": "Можно отметить как найденного только водителя"}
            
            if participant.is_found:
                return {"success": False, "error": "Участник уже отмечен как найденный"}
            
            # Отмечаем как найденного
            participant.is_found = True
            participant.found_at = datetime.now()
            
            db.commit()
            
            logger.info(f"Админ {admin_user_id} вручную отметил участника {participant_id} как найденного в игре {game_id}")
            
            return {
                "success": True,
                "message": f"Участник {participant.user.name} отмечен как найденный",
                "found_at": participant.found_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при отметке участника как найденного: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    @staticmethod
    def manual_mark_participant_eliminated(game_id: int, participant_id: int, admin_user_id: int) -> Dict[str, Any]:
        """Ручная отметка участника как выбывшего"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            participant = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.id == participant_id
            ).first()
            
            if not participant:
                return {"success": False, "error": "Участник не найден"}
            
            # Отмечаем как выбывшего (убираем флаг найденного, если был)
            participant.is_found = True  # Выбывший считается найденным
            participant.found_at = datetime.now()
            
            db.commit()
            
            logger.info(f"Админ {admin_user_id} вручную отметил участника {participant_id} как выбывшего в игре {game_id}")
            
            return {
                "success": True,
                "message": f"Участник {participant.user.name} отмечен как выбывший",
                "eliminated_at": participant.found_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при отметке участника как выбывшего: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    @staticmethod
    def get_game_control_info(game_id: int) -> Dict[str, Any]:
        """Получить информацию о игре для ручного управления"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return {"success": False, "error": "Игра не найдена"}
            
            # Собираем информацию об участниках
            participants_info = []
            for participant in game.participants:
                participant_data = {
                    "id": participant.id,
                    "user_id": participant.user_id,
                    "user_name": participant.user.name,
                    "role": participant.role.value if participant.role else None,
                    "is_found": participant.is_found,
                    "has_hidden": participant.has_hidden,
                    "is_ready": participant.is_ready,
                    "found_at": participant.found_at.isoformat() if participant.found_at else None,
                    "hidden_at": participant.hidden_at.isoformat() if participant.hidden_at else None
                }
                participants_info.append(participant_data)
            
            # Подсчитываем статистику
            drivers = [p for p in game.participants if p.role == GameRole.DRIVER]
            seekers = [p for p in game.participants if p.role == GameRole.SEEKER]
            found_drivers = [p for p in drivers if p.is_found]
            hidden_drivers = [p for p in drivers if p.has_hidden]
            
            return {
                "success": True,
                "game": {
                    "id": game.id,
                    "status": game.status.value,
                    "district": game.district,
                    "scheduled_at": game.scheduled_at.isoformat(),
                    "started_at": game.started_at.isoformat() if game.started_at else None,
                    "ended_at": game.ended_at.isoformat() if game.ended_at else None,
                    "participants_count": len(game.participants),
                    "max_participants": game.max_participants,
                    "max_drivers": game.max_drivers
                },
                "participants": participants_info,
                "statistics": {
                    "total_drivers": len(drivers),
                    "total_seekers": len(seekers),
                    "found_drivers": len(found_drivers),
                    "hidden_drivers": len(hidden_drivers),
                    "remaining_drivers": len(drivers) - len(found_drivers)
                },
                "control_options": ManualGameControlService._get_available_actions(game)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации для управления игрой: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    @staticmethod
    def _get_available_actions(game: Game) -> List[str]:
        """Получить список доступных действий для управления игрой"""
        actions = []
        
        if game.status == GameStatus.UPCOMING:
            actions.extend(["assign_roles", "start_hiding_phase", "cancel_game"])
        elif game.status == GameStatus.HIDING_PHASE:
            actions.extend(["start_searching_phase", "mark_participant", "end_game"])
        elif game.status == GameStatus.SEARCHING_PHASE:
            actions.extend(["mark_participant", "end_game"])
        elif game.status == GameStatus.RECRUITING:
            actions.extend(["cancel_game"])
        
        return actions
    
    @staticmethod
    def reassign_participant_role(game_id: int, participant_id: int, new_role: GameRole, admin_user_id: int) -> Dict[str, Any]:
        """Переназначить роль участника"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            participant = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.id == participant_id
            ).first()
            
            if not participant:
                return {"success": False, "error": "Участник не найден"}
            
            game = participant.game
            if game.status not in [GameStatus.RECRUITING, GameStatus.UPCOMING]:
                return {"success": False, "error": "Нельзя изменять роли после начала игры"}
            
            old_role = participant.role
            participant.role = new_role
            
            db.commit()
            
            logger.info(f"Админ {admin_user_id} изменил роль участника {participant_id} с {old_role} на {new_role} в игре {game_id}")
            
            return {
                "success": True,
                "message": f"Роль участника {participant.user.name} изменена на {new_role.value}",
                "old_role": old_role.value if old_role else None,
                "new_role": new_role.value
            }
            
        except Exception as e:
            logger.error(f"Ошибка при переназначении роли: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close() 