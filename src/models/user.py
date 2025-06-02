from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, BigInteger
from sqlalchemy.sql import func
import enum
from datetime import datetime

from src.models.base import Base

class UserRole(enum.Enum):
    """Перечисление ролей пользователя"""
    PLAYER = "player"  # Игрок
    DRIVER = "driver"  # Водитель
    OBSERVER = "observer"  # Наблюдатель

class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, index=True)
    name = Column(String, nullable=False)
    phone = Column(String)
    district = Column(String, nullable=False)
    default_role = Column(Enum(UserRole), default=UserRole.PLAYER)
    
    # Флаг согласия с правилами
    rules_accepted = Column(Boolean, default=False)
    
    # Поля для аудита
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, role={self.default_role})>" 