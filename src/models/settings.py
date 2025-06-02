from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime

from src.models.base import Base

class District(Base):
    """Модель района"""
    __tablename__ = "districts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    
    # Поля для аудита
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<District(id={self.id}, name={self.name}, active={self.is_active})>"

class DistrictZone(Base):
    """Модель зоны района для игр"""
    __tablename__ = "district_zones"
    
    id = Column(Integer, primary_key=True, index=True)
    district_name = Column(String, ForeignKey("districts.name"), nullable=False, index=True)
    
    # Название зоны
    zone_name = Column(String, nullable=False)  # Например: "Центр города", "Парк Горького"
    
    # Геоданные зоны
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False) 
    radius = Column(Integer, nullable=False)  # Радиус в метрах
    
    # Статус и настройки
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Зона по умолчанию для района
    
    # Дополнительная информация
    description = Column(Text, nullable=True)
    
    # Связи
    district = relationship("District", backref="zones")
    
    # Поля для аудита
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    @property
    def area_km2(self) -> float:
        """Площадь зоны в км²"""
        return round((3.14159 * (self.radius / 1000) ** 2), 2)
    
    def __repr__(self):
        return f"<DistrictZone(id={self.id}, district={self.district_name}, zone={self.zone_name})>"

class Role(Base):
    """Модель роли"""
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    
    # Поля для аудита
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name}, active={self.is_active})>"

class GameRule(Base):
    """Модель правил игры"""
    __tablename__ = "game_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    
    # Поля для аудита
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<GameRule(id={self.id}, version={self.version}, active={self.is_active})>" 