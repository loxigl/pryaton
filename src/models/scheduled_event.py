from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from src.models.base import Base

class EventType(enum.Enum):
    """Типы запланированных событий"""
    REMINDER_60MIN = "reminder_60min"
    REMINDER_24HOUR = "reminder_24hour"
    REMINDER_5MIN = "reminder_5min"
    GAME_START = "game_start"
    HIDING_PHASE_END = "hiding_phase_end"
    SEARCH_PHASE_END = "search_phase_end"
    GAME_CLEANUP = "game_cleanup"

class ScheduledEvent(Base):
    """Модель запланированного события планировщика"""
    __tablename__ = "scheduled_events"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Связь с игрой
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    game = relationship("Game", lazy="joined")
    
    # Тип события
    event_type = Column(String(50), nullable=False)
    
    # Запланированное время выполнения
    scheduled_at = Column(DateTime, nullable=False, index=True)
    
    # Параметры события (JSON)
    event_data = Column(JSON, nullable=True)
    
    # Статус выполнения
    is_executed = Column(Boolean, default=False, index=True)
    
    # Время фактического выполнения
    executed_at = Column(DateTime, nullable=True)
    
    # Время создания записи
    created_at = Column(DateTime, default=datetime.now)
    
    # Уникальность по игре, типу события и времени
    __table_args__ = (
        UniqueConstraint('game_id', 'event_type', 'scheduled_at', name='_game_event_time_uc'),
    )
    
    def __repr__(self):
        return f"<ScheduledEvent(id={self.id}, game_id={self.game_id}, type={self.event_type}, scheduled_at={self.scheduled_at}, executed={self.is_executed})>"
    
    @property
    def is_overdue(self) -> bool:
        """Проверяет, просрочено ли событие"""
        return self.scheduled_at < datetime.now() and not self.is_executed
    
    @property
    def job_id(self) -> str:
        """Генерирует ID задачи для планировщика"""
        return f"{self.event_type}_{self.game_id}_{self.id}" 