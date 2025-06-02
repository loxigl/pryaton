from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from src.models.base import Base

class GameStatus(enum.Enum):
    """Перечисление статусов игры"""
    RECRUITING = "recruiting"  # Набор участников
    UPCOMING = "upcoming"  # Игра скоро начнется
    IN_PROGRESS = "in_progress"  # Игра в процессе
    COMPLETED = "completed"  # Игра завершена
    CANCELED = "canceled"  # Игра отменена

class GameRole(enum.Enum):
    """Перечисление ролей в игре"""
    DRIVER = "driver"  # Водитель
    SEEKER = "seeker"  # Искатель

class Game(Base):
    """Модель игры"""
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Основные параметры игры
    district = Column(String, nullable=False)  # Район проведения
    max_participants = Column(Integer, nullable=False)
    max_drivers = Column(Integer, default=1)  # Максимальное количество водителей
    max_seekers = Column(Integer, nullable=True)  # Максимальное количество искателей (автовычисляется)
    status = Column(Enum(GameStatus), default=GameStatus.RECRUITING)
    
    # Временные параметры
    scheduled_at = Column(DateTime, nullable=False)  # Запланированное время
    started_at = Column(DateTime, nullable=True)  # Фактическое время начала
    ended_at = Column(DateTime, nullable=True)  # Время завершения
    
    # Создатель игры (админ)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    creator = relationship("User", foreign_keys=[creator_id])
    
    # Зона пряток
    zone_center_lat = Column(Float, nullable=True)  # Центр зоны - широта
    zone_center_lon = Column(Float, nullable=True)  # Центр зоны - долгота
    zone_radius = Column(Integer, nullable=True)    # Радиус зоны в метрах
    
    # Дополнительная информация
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Связи
    participants = relationship("GameParticipant", back_populates="game", lazy="joined")
    
    # Поля для аудита
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    @property
    def calculated_max_seekers(self) -> int:
        """Вычисляет максимальное количество искателей"""
        return self.max_participants - self.max_drivers
    
    @property
    def has_game_zone(self) -> bool:
        """Проверяет, задана ли игровая зона"""
        return (self.zone_center_lat is not None and 
                self.zone_center_lon is not None and 
                self.zone_radius is not None and self.zone_radius > 0)
    
    @property
    def zone_info(self) -> dict:
        """Возвращает информацию о игровой зоне"""
        if not self.has_game_zone:
            return {"error": "Игровая зона не задана"}
        
        return {
            "center_lat": self.zone_center_lat,
            "center_lon": self.zone_center_lon,
            "radius": self.zone_radius,
            "area_km2": round((3.14159 * (self.zone_radius / 1000) ** 2), 2)
        }
    
    def set_game_zone(self, lat: float, lon: float, radius: int) -> None:
        """Устанавливает игровую зону"""
        if radius <= 0:
            raise ValueError("Радиус зоны должен быть больше 0")
        if not (-90 <= lat <= 90):
            raise ValueError("Широта должна быть в диапазоне от -90 до 90")
        if not (-180 <= lon <= 180):
            raise ValueError("Долгота должна быть в диапазоне от -180 до 180")
            
        self.zone_center_lat = lat
        self.zone_center_lon = lon
        self.zone_radius = radius
    
    def __repr__(self):
        return f"<Game(id={self.id}, district={self.district}, status={self.status})>"

class GameParticipant(Base):
    """Модель участника игры"""
    __tablename__ = "game_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Связи с игрой и пользователем
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Обратные ссылки
    game = relationship("Game", back_populates="participants",lazy="joined")
    user = relationship("User",lazy="joined")
    
    # Роль в игре
    role = Column(Enum(GameRole), nullable=True)
    
    # Статусы участия
    is_ready = Column(Boolean, default=False)  # Готов к игре
    is_found = Column(Boolean, default=False)  # Найден (для искателей)
    
    # Время обнаружения
    found_at = Column(DateTime)
    
    # Поля для аудита
    joined_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<GameParticipant(game_id={self.game_id}, user_id={self.user_id}, role={self.role})>"

class Location(Base):
    """Модель геолокации"""
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Связи с игрой и пользователем
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Координаты
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    # Время фиксации
    timestamp = Column(DateTime, default=datetime.now)
    
    # Тип точки (старт, чекпоинт, финиш)
    location_type = Column(String)
    
    def __repr__(self):
        return f"<Location(game_id={self.game_id}, user_id={self.user_id}, lat={self.latitude}, lon={self.longitude})>"

class Photo(Base):
    """Модель фотографии"""
    __tablename__ = "photos"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Связи с игрой и пользователем
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Информация о фото
    file_id = Column(String, nullable=False)  # Идентификатор файла в Telegram
    description = Column(Text)
    
    # Статус проверки (принято/отклонено)
    is_approved = Column(Boolean, nullable=True)
    
    # Время загрузки
    uploaded_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Photo(game_id={self.game_id}, user_id={self.user_id}, approved={self.is_approved})>" 