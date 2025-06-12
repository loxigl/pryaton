from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from src.models.base import Base
from src.models.user import UserRole

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

class RoleDisplay(Base):
    """Модель отображения роли"""
    __tablename__ = "role_displays"
    
    id = Column(Integer, primary_key=True, index=True)
    role = Column(Enum(UserRole), unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    
    # Поля для аудита
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<RoleDisplay(role={self.role}, display_name={self.display_name})>"

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

class GameSettings(Base):
    """Модель настроек игры"""
    __tablename__ = "game_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Настройки автоматизации
    auto_start_game = Column(Boolean, default=True)  # Автостарт игры по времени
    auto_start_hiding = Column(Boolean, default=True)  # Автостарт фазы пряток
    auto_start_searching = Column(Boolean, default=True)  # Автостарт фазы поиска
    auto_assign_roles = Column(Boolean, default=True)  # Автораспределение ролей
    auto_end_game = Column(Boolean, default=True)  # Автозавершение игры
    
    # Временные настройки (в минутах)
    hiding_phase_duration = Column(Integer, default=15)  # Длительность фазы пряток
    searching_phase_duration = Column(Integer, default=60)  # Длительность фазы поиска
    game_start_notification_time = Column(Integer, default=10)  # За сколько минут уведомлять о старте
    
    # Настройки для ручного управления
    manual_control_mode = Column(Boolean, default=False)  # Полное ручное управление
    require_admin_approval = Column(Boolean, default=False)  # Требовать подтверждение админа для действий
    
    # Настройки уведомлений
    notify_on_role_assignment = Column(Boolean, default=True)
    notify_on_phase_change = Column(Boolean, default=True)
    notify_on_participant_action = Column(Boolean, default=True)
    
    # Дополнительные настройки
    allow_early_start = Column(Boolean, default=True)  # Разрешить досрочный старт
    min_participants_to_start = Column(Integer, default=3)  # Минимум участников для старта
    
    # Поля для аудита
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<GameSettings(id={self.id}, manual_control={self.manual_control_mode})>" 