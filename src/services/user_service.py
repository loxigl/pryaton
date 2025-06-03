from src.models.game import GameParticipant
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
import os
from loguru import logger

from src.models.base import get_db
from src.models.user import User, UserRole

class UserService:
    """Сервис для работы с пользователями"""
    
    @staticmethod
    def get_user_by_telegram_id(telegram_id: int) -> Tuple[User, List[GameParticipant]]:
        """Получение пользователя по Telegram ID"""
        db_generator = get_db()
        db = next(db_generator)
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        participations = db.query(GameParticipant).filter(GameParticipant.user_id == user.id).all() if user else []
        return user, participations
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Tuple[User, List[GameParticipant]]:
        """Получение пользователя по внутреннему ID"""
        db_generator = get_db()
        db = next(db_generator)
        user = db.query(User).filter(User.id == user_id).first()
        participations = db.query(GameParticipant).filter(GameParticipant.user_id == user_id).all() if user else []
        return user, participations
    
    @staticmethod
    def create_user(
        telegram_id: int,
        username: str,
        name: str,
        phone: Optional[str],
        district: str,
        default_role: UserRole,
        rules_accepted: bool = False
    ) -> User:
        """Создание нового пользователя"""
        db_generator = get_db()
        db = next(db_generator)
        
        user = User(
            telegram_id=telegram_id,
            username=username,
            name=name,
            phone=phone,
            district=district,
            default_role=default_role,
            rules_accepted=rules_accepted
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def update_user(user_id: int, **kwargs) -> Optional[User]:
        """Обновление данных пользователя"""
        db_generator = get_db()
        db = next(db_generator)
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def is_admin(telegram_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        admin_ids = os.getenv("ADMIN_USER_IDS", "").split(",")
        return str(telegram_id) in admin_ids
    
    @staticmethod
    def get_all_users() -> List[User]:
        """Получение списка всех пользователей"""
        db_generator = get_db()
        db = next(db_generator)
        return db.query(User).all()
    
    @staticmethod
    def get_users_by_district(district: str) -> List[User]:
        """Получение списка пользователей по району"""
        db_generator = get_db()
        db = next(db_generator)
        return db.query(User).filter(User.district == district).all() 
    
    @staticmethod
    def get_admin_users() -> List[User]:
        """Получение списка администраторов"""
        db_generator = get_db()
        db = next(db_generator)
        admin_ids = os.getenv("ADMIN_USER_IDS", "").split(",")
        return db.query(User).filter(User.telegram_id.in_(admin_ids)).all()