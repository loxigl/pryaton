from src.models.base import Base, engine
from src.models.user import User, UserRole
from src.models.game import Game, GameParticipant, GameStatus, GameRole, Location, Photo
from src.models.settings import District, DistrictZone, Role, GameRule, GameSettings
from src.models.scheduled_event import ScheduledEvent, EventType

def create_tables():
    """Создание всех таблиц в базе данных"""
    Base.metadata.create_all(bind=engine)

__all__ = [
    "create_tables",
    "User", "UserRole",
    "Game", "GameParticipant", "GameStatus", "GameRole", "Location", "Photo",
    "District", "DistrictZone", "Role", "GameRule", "GameSettings",
    "ScheduledEvent", "EventType"
] 