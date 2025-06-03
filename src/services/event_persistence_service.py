from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from loguru import logger
from sqlalchemy.orm import Session

from src.models.base import get_db
from src.models.scheduled_event import ScheduledEvent, EventType
from src.models.game import Game, GameStatus


class EventPersistenceService:
    """Сервис для управления персистентными событиями планировщика"""
    
    @staticmethod
    def save_event(
        game_id: int,
        event_type: str,
        scheduled_at: datetime,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Optional[ScheduledEvent]:
        """Сохранение события в БД"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            try:
                # Проверяем, не существует ли уже такое событие
                existing_event = db.query(ScheduledEvent).filter_by(
                    game_id=game_id,
                    event_type=event_type,
                    scheduled_at=scheduled_at
                ).first()
                
                if existing_event:
                    logger.warning(f"Событие уже существует: {existing_event}")
                    return existing_event
                
                # Создаем новое событие
                new_event = ScheduledEvent(
                    game_id=game_id,
                    event_type=event_type,
                    scheduled_at=scheduled_at,
                    event_data=event_data or {}
                )
                
                db.add(new_event)
                db.commit()
                db.refresh(new_event)
                
                logger.info(f"Сохранено событие: {new_event}")
                return new_event
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка сохранения события: {e}")
            return None
    
    @staticmethod
    def get_pending_events() -> List[ScheduledEvent]:
        """Получение всех невыполненных событий"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            try:
                events = db.query(ScheduledEvent).filter_by(
                    is_executed=False
                ).order_by(ScheduledEvent.scheduled_at).all()
                
                return events
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения невыполненных событий: {e}")
            return []
    
    @staticmethod
    def get_game_events(game_id: int, include_executed: bool = False) -> List[ScheduledEvent]:
        """Получение событий для конкретной игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            try:
                query = db.query(ScheduledEvent).filter_by(game_id=game_id)
                
                if not include_executed:
                    query = query.filter_by(is_executed=False)
                
                events = query.order_by(ScheduledEvent.scheduled_at).all()
                return events
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения событий для игры {game_id}: {e}")
            return []
    
    @staticmethod
    def mark_event_executed(event_id: int) -> bool:
        """Отметка события как выполненного"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            try:
                event = db.query(ScheduledEvent).filter_by(id=event_id).first()
                
                if not event:
                    logger.warning(f"Событие {event_id} не найдено")
                    return False
                
                event.is_executed = True
                event.executed_at = datetime.now()
                
                db.commit()
                logger.info(f"Событие {event_id} отмечено как выполненное")
                return True
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка отметки события {event_id} как выполненного: {e}")
            return False
    
    @staticmethod
    def cancel_game_events(game_id: int) -> int:
        """Отмена всех событий для игры (отметка как выполненные)"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            try:
                events = db.query(ScheduledEvent).filter_by(
                    game_id=game_id,
                    is_executed=False
                ).all()
                
                cancelled_count = 0
                for event in events:
                    event.is_executed = True
                    event.executed_at = datetime.now()
                    cancelled_count += 1
                
                db.commit()
                logger.info(f"Отменено {cancelled_count} событий для игры {game_id}")
                return cancelled_count
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка отмены событий для игры {game_id}: {e}")
            return 0
    
    @staticmethod
    def cleanup_old_events(days_old: int = 7) -> int:
        """Очистка старых выполненных событий"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            try:
                cutoff_date = datetime.now() - timedelta(days=days_old)
                
                old_events = db.query(ScheduledEvent).filter(
                    ScheduledEvent.is_executed == True,
                    ScheduledEvent.executed_at < cutoff_date
                ).all()
                
                count = len(old_events)
                
                for event in old_events:
                    db.delete(event)
                
                db.commit()
                logger.info(f"Удалено {count} старых событий (старше {days_old} дней)")
                return count
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка очистки старых событий: {e}")
            return 0
    
    @staticmethod
    def get_events_statistics() -> Dict[str, Any]:
        """Получение статистики по событиям"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            try:
                total_events = db.query(ScheduledEvent).count()
                executed_events = db.query(ScheduledEvent).filter_by(is_executed=True).count()
                pending_events = db.query(ScheduledEvent).filter_by(is_executed=False).count()
                
                overdue_events = db.query(ScheduledEvent).filter(
                    ScheduledEvent.is_executed == False,
                    ScheduledEvent.scheduled_at < datetime.now()
                ).count()
                
                return {
                    "total": total_events,
                    "executed": executed_events,
                    "pending": pending_events,
                    "overdue": overdue_events
                }
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики событий: {e}")
            return {"total": 0, "executed": 0, "pending": 0, "overdue": 0}
    
    @staticmethod
    def update_game_events(game_id: int, new_scheduled_at: datetime):
        """Обновление времени событий при изменении времени игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            try:
                # Получаем игру для вычисления новых времен
                game = db.query(Game).filter_by(id=game_id).first()
                if not game:
                    logger.error(f"Игра {game_id} не найдена")
                    return False
                
                # Отменяем старые события
                EventPersistenceService.cancel_game_events(game_id)
                
                # Пересоздаем события с новым временем
                # Это будет вызвано из scheduler_service
                logger.info(f"События для игры {game_id} будут пересозданы с новым временем: {new_scheduled_at}")
                return True
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка обновления событий для игры {game_id}: {e}")
            return False 
    @staticmethod
    def get_all_events() -> List[ScheduledEvent]:
        """Получение всех событий"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            events = db.query(ScheduledEvent).all()
            return events
        except Exception as e:
            logger.error(f"Ошибка получения всех событий: {e}")
            return []