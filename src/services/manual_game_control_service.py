from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger
from datetime import datetime

from src.models.base import get_db
from src.models.game import Game, GameParticipant, GameStatus, GameRole
from src.models.user import User
from src.services.game_settings_service import GameSettingsService
from src.services.game_service import GameService
from src.services.user_service import UserService

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
            
            # КРИТИЧЕСКИ ВАЖНО: Проверяем завершение игры после изменения статуса
            # Импортируем GameService здесь, чтобы избежать циклических импортов
            try:
                from src.services.game_service import GameService
                # Проверяем, нужно ли завершить игру после изменения статуса
                if GameService._check_auto_game_completion(game_id):
                    logger.info(f"Игра {game_id} автоматически завершена после ручной отметки участника {participant_id}")
            except Exception as completion_error:
                logger.warning(f"Ошибка при проверке завершения игры {game_id}: {completion_error}")
            
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
            
            # КРИТИЧЕСКИ ВАЖНО: Проверяем завершение игры после изменения статуса
            try:
                from src.services.game_service import GameService
                # Проверяем, нужно ли завершить игру после изменения статуса
                if GameService._check_auto_game_completion(game_id):
                    logger.info(f"Игра {game_id} автоматически завершена после отметки участника {participant_id} как выбывшего")
            except Exception as completion_error:
                logger.warning(f"Ошибка при проверке завершения игры {game_id}: {completion_error}")
            
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
    def manual_unmark_participant_found(game_id: int, participant_id: int, admin_user_id: int) -> Dict[str, Any]:
        """Ручная отмена отметки участника как найденного"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            participant = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.id == participant_id
            ).first()
            
            if not participant:
                return {"success": False, "error": "Участник не найден"}
            
            if not participant.is_found:
                return {"success": False, "error": "Участник не отмечен как найденный"}
            
            # Убираем отметку найденного
            participant.is_found = False
            participant.found_at = None
            
            db.commit()
            
            logger.info(f"Админ {admin_user_id} отменил отметку найденного для участника {participant_id} в игре {game_id}")
            
            # ВАЖНО: После отмены отметки игра может продолжиться, но проверим состояние
            try:
                from src.services.game_service import GameService
                game = db.query(Game).filter(Game.id == game_id).first()
                if game and game.status == GameStatus.COMPLETED:
                    # Если игра была завершена, возвращаем её в активное состояние
                    game.status = GameStatus.SEARCHING_PHASE
                    game.ended_at = None
                    db.commit()
                    logger.info(f"Игра {game_id} возвращена в активное состояние после отмены отметки участника")
            except Exception as status_error:
                logger.warning(f"Ошибка при обновлении статуса игры {game_id}: {status_error}")
            
            return {
                "success": True,
                "message": f"Отметка найденного для участника {participant.user.name} отменена"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при отмене отметки найденного: {e}")
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

    @staticmethod
    def add_participant_to_game(game_id: int, user_id: int, admin_user_id: int) -> Dict[str, Any]:
        """Добавление участника в игру"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            # Проверяем существование игры
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return {"success": False, "error": "Игра не найдена"}
            
            # Проверяем, что игра не завершена
            if game.status in [GameStatus.COMPLETED, GameStatus.CANCELED]:
                return {"success": False, "error": "Нельзя добавлять участников в завершенную игру"}
            
            # Проверяем, что пользователь существует
            user, _ = UserService.get_user_by_id(user_id)
            if not user:
                return {"success": False, "error": "Пользователь не найден"}
            
            # Проверяем, что пользователь еще не участвует
            existing_participant = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.user_id == user_id
            ).first()
            
            if existing_participant:
                return {"success": False, "error": f"Пользователь {user.name} уже участвует в игре"}
            
            # Проверяем лимит участников
            current_participants = len(game.participants)
            if current_participants >= game.max_participants:
                return {"success": False, "error": f"Достигнут лимит участников ({game.max_participants})"}
            
            # Добавляем участника
            participant = GameService.join_game(game_id, user_id)
            if not participant:
                return {"success": False, "error": "Не удалось добавить участника"}
            
            # ПРИМЕЧАНИЕ: Роли НЕ назначаются сразу при добавлении участника
            # Они будут назначены автоматически при запуске игры через GameService.assign_roles()
            # Это позволяет администратору контролировать состав участников перед назначением ролей
            
            # ИСКЛЮЧЕНИЕ: Если в игре уже есть участники с назначенными ролями,
            # назначаем роль новому участнику, чтобы не сломать возможность запуска игры
            participants_with_roles = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.role.isnot(None)
            ).count()
            
            if participants_with_roles > 0:
                # Роли уже распределены, назначаем роль новому участнику
                try:
                    current_drivers = sum(1 for p in game.participants if p.role == GameRole.DRIVER)
                    
                    if current_drivers < game.max_drivers:
                        participant.role = GameRole.DRIVER
                        logger.info(f"Новому участнику {user_id} назначена роль DRIVER (роли уже распределены)")
                    else:
                        participant.role = GameRole.SEEKER
                        logger.info(f"Новому участнику {user_id} назначена роль SEEKER (роли уже распределены)")
                    
                    db.commit()
                    
                except Exception as role_error:
                    logger.warning(f"Ошибка при назначении роли новому участнику: {role_error}")
            
            logger.info(f"Админ {admin_user_id} добавил участника {user_id} ({user.name}) в игру {game_id}")
            
            # ВАЖНО: Проверяем и обновляем статус игры после добавления участника
            try:
                # Получаем актуальное количество участников после добавления
                updated_game = db.query(Game).filter(Game.id == game_id).first()
                actual_participants = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
                
                # Если достигнут лимит участников, переводим игру в UPCOMING
                if actual_participants >= updated_game.max_participants and updated_game.status == GameStatus.RECRUITING:
                    updated_game.status = GameStatus.UPCOMING
                    db.commit()
                    logger.info(f"Игра {game_id} автоматически переведена в статус UPCOMING после добавления участника (участников: {actual_participants}/{updated_game.max_participants})")
                    
            except Exception as status_error:
                logger.warning(f"Ошибка при обновлении статуса игры {game_id} после добавления участника: {status_error}")
            
            return {
                "success": True,
                "message": f"Участник {user.name} добавлен в игру",
                "participant_id": participant.id,
                "participant_name": user.name
            }
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении участника: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    @staticmethod
    def remove_participant_from_game(game_id: int, participant_id: int, admin_user_id: int) -> Dict[str, Any]:
        """Удаление участника из игры"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            # Находим участника
            participant = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.id == participant_id
            ).first()
            
            if not participant:
                return {"success": False, "error": "Участник не найден"}
            
            # Проверяем статус игры
            game = participant.game
            if game.status in [GameStatus.COMPLETED, GameStatus.CANCELED]:
                return {"success": False, "error": "Нельзя удалять участников из завершенной игры"}
            
            # Сохраняем имя для сообщения
            participant_name = participant.user.name
            
            # Удаляем участника
            db.delete(participant)
            db.commit()
            
            logger.info(f"Админ {admin_user_id} удалил участника {participant_id} ({participant_name}) из игры {game_id}")
            
            # ВАЖНО: После удаления участника проверяем логику игры
            try:
                # Получаем актуальное количество участников после удаления
                updated_game = db.query(Game).filter(Game.id == game_id).first()
                actual_participants = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
                
                # Если игра была в UPCOMING, но участников стало меньше лимита, переводим в RECRUITING
                if updated_game.status == GameStatus.UPCOMING and actual_participants < updated_game.max_participants:
                    updated_game.status = GameStatus.RECRUITING
                    db.commit()
                    logger.info(f"Игра {game_id} автоматически переведена в статус RECRUITING после удаления участника (участников: {actual_participants}/{updated_game.max_participants})")
                
                # Если удален водитель, который был найден, это может повлиять на завершение игры
                if participant.role == GameRole.DRIVER and participant.is_found:
                    if updated_game.status == GameStatus.COMPLETED:
                        # Если игра завершена, но водитель удален, возвращаем в активное состояние
                        remaining_drivers = [p for p in updated_game.participants if p.role == GameRole.DRIVER]
                        unfound_drivers = [p for p in remaining_drivers if not p.is_found]
                        
                        if unfound_drivers:  # Есть ненайденные водители
                            updated_game.status = GameStatus.SEARCHING_PHASE
                            updated_game.ended_at = None
                            db.commit()
                            logger.info(f"Игра {game_id} возвращена в активное состояние после удаления найденного водителя")
                            
            except Exception as logic_error:
                logger.warning(f"Ошибка при проверке логики игры после удаления участника: {logic_error}")
            
            return {
                "success": True,
                "message": f"Участник {participant_name} удален из игры"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при удалении участника: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    @staticmethod
    def get_available_users_for_game(game_id: int) -> List[Dict[str, Any]]:
        """Получить список пользователей, доступных для добавления в игру"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            # Получаем всех пользователей, которые еще не участвуют в игре
            existing_participants = db.query(GameParticipant.user_id).filter(
                GameParticipant.game_id == game_id
            ).subquery()
            
            available_users = db.query(User).filter(
                ~User.id.in_(existing_participants)
            ).all()
            
            result = []
            for user in available_users:
                result.append({
                    "id": user.id,
                    "name": user.name,
                    "phone": user.phone,
                    "district": user.district
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении доступных пользователей: {e}")
            return []
        finally:
            db.close()

    @staticmethod
    def validate_role_distribution(game_id: int, role_assignments: Dict[int, GameRole]) -> Dict[str, Any]:
        """Валидация распределения ролей"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return {"success": False, "error": "Игра не найдена"}
            
            # Подсчитываем роли
            driver_count = sum(1 for role in role_assignments.values() if role == GameRole.DRIVER)
            seeker_count = sum(1 for role in role_assignments.values() if role == GameRole.SEEKER)
            total_assigned = len(role_assignments)
            total_participants = len(game.participants)
            
            # Проверки
            if total_assigned != total_participants:
                return {"success": False, "error": f"Не всем участникам назначены роли: {total_assigned}/{total_participants}"}
            
            if driver_count > game.max_drivers:
                return {"success": False, "error": f"Слишком много водителей: {driver_count}/{game.max_drivers}"}
            
            if driver_count == 0:
                return {"success": False, "error": "Должен быть хотя бы 1 водитель"}
            
            if seeker_count == 0:
                return {"success": False, "error": "Должен быть хотя бы 1 искатель"}
            
            return {
                "success": True,
                "driver_count": driver_count,
                "seeker_count": seeker_count,
                "max_drivers": game.max_drivers
            }
            
        except Exception as e:
            logger.error(f"Ошибка при валидации ролей: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    @staticmethod
    def manual_assign_roles(game_id: int, role_assignments: Dict[int, GameRole], admin_user_id: int) -> Dict[str, Any]:
        """Ручное распределение ролей"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            # Валидируем распределение
            validation = ManualGameControlService.validate_role_distribution(game_id, role_assignments)
            if not validation["success"]:
                return validation
            
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return {"success": False, "error": "Игра не найдена"}
            
            if game.status not in [GameStatus.RECRUITING, GameStatus.UPCOMING]:
                return {"success": False, "error": "Нельзя назначать роли после начала игры"}
            
            # Назначаем роли
            assigned_participants = []
            for participant_id, role in role_assignments.items():
                participant = db.query(GameParticipant).filter(
                    GameParticipant.game_id == game_id,
                    GameParticipant.id == participant_id
                ).first()
                
                if participant:
                    participant.role = role
                    assigned_participants.append({
                        "participant_id": participant_id,
                        "user_name": participant.user.name,
                        "role": role.value
                    })
            
            db.commit()
            
            logger.info(f"Админ {admin_user_id} вручную назначил роли в игре {game_id}: {validation['driver_count']} водителей, {validation['seeker_count']} искателей")
            
            return {
                "success": True,
                "message": f"Роли успешно назначены: {validation['driver_count']} водителей, {validation['seeker_count']} искателей",
                "assigned_participants": assigned_participants,
                "driver_count": validation["driver_count"],
                "seeker_count": validation["seeker_count"]
            }
            
        except Exception as e:
            logger.error(f"Ошибка при ручном назначении ролей: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    @staticmethod
    def get_manual_role_assignment_info(game_id: int) -> Dict[str, Any]:
        """Получить информацию для ручного назначения ролей"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return {"success": False, "error": "Игра не найдена"}
            
            if game.status not in [GameStatus.RECRUITING, GameStatus.UPCOMING]:
                return {"success": False, "error": "Нельзя назначать роли после начала игры"}
            
            participants = []
            for participant in game.participants:
                participants.append({
                    "id": participant.id,
                    "user_id": participant.user_id,
                    "user_name": participant.user.name,
                    "current_role": participant.role.value if participant.role else None,
                    "district": participant.user.district
                })
            
            return {
                "success": True,
                "game_id": game_id,
                "participants": participants,
                "max_drivers": game.max_drivers,
                "max_participants": game.max_participants,
                "current_driver_count": sum(1 for p in participants if p["current_role"] == "driver"),
                "current_seeker_count": sum(1 for p in participants if p["current_role"] == "seeker")
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации для назначения ролей: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close() 