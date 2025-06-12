from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import json
import os
from loguru import logger

from src.models.base import get_db
from src.models.settings import District, GameRule, RoleDisplay
from src.models.user import UserRole

class SettingsService:
    """Сервис для управления настройками системы"""
    
    # Дефолтные отображения ролей
    DEFAULT_ROLE_DISPLAYS = {
        UserRole.PLAYER: "🔍 Игрок",
        UserRole.DRIVER: "🚗 Водитель",
        UserRole.OBSERVER: "👁 Наблюдатель"
    }
    
    @staticmethod
    def _get_or_create_default_districts() -> None:
        """Создает дефолтные районы если их нет в БД"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Проверяем есть ли районы в БД
        if db.query(District).count() == 0:
            default_districts = [
             "Тестовый район"
            ]
            
            for district_name in default_districts:
                district = District(name=district_name, is_active=True)
                db.add(district)
            
            db.commit()
            logger.info(f"Созданы дефолтные районы: {len(default_districts)} шт.")
    
    @staticmethod
    def _get_or_create_default_role_displays() -> None:
        """Создает дефолтные отображения ролей если их нет в БД"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Проверяем есть ли отображения ролей в БД
        if db.query(RoleDisplay).count() == 0:
            for role, display_name in SettingsService.DEFAULT_ROLE_DISPLAYS.items():
                role_display = RoleDisplay(role=role, display_name=display_name)
                db.add(role_display)
            
            db.commit()
            logger.info(f"Созданы дефолтные отображения ролей: {len(SettingsService.DEFAULT_ROLE_DISPLAYS)} шт.")
    
    @staticmethod
    def get_districts() -> List[str]:
        """Получение списка активных районов"""
        SettingsService._get_or_create_default_districts()
        
        db_generator = get_db()
        db = next(db_generator)
        
        districts = db.query(District).filter(District.is_active == True).order_by(District.name).all()
        return [district.name for district in districts]
    
    @staticmethod
    def get_all_districts() -> List[District]:
        """Получение всех районов (включая неактивные)"""
        SettingsService._get_or_create_default_districts()
        
        db_generator = get_db()
        db = next(db_generator)
        
        return db.query(District).order_by(District.name).all()
    
    @staticmethod
    def get_available_roles() -> List[str]:
        """Получение списка доступных ролей"""
        SettingsService._get_or_create_default_role_displays()
        
        db_generator = get_db()
        db = next(db_generator)
        
        role_displays = db.query(RoleDisplay).all()
        return [role_display.display_name for role_display in role_displays]
    
    @staticmethod
    def get_role_display_name(role: UserRole) -> str:
        """Получить отображаемое имя для роли"""
        SettingsService._get_or_create_default_role_displays()
        
        db_generator = get_db()
        db = next(db_generator)
        
        role_display = db.query(RoleDisplay).filter(RoleDisplay.role == role).first()
        if role_display:
            return role_display.display_name
        return SettingsService.DEFAULT_ROLE_DISPLAYS.get(role, str(role))
    
    @staticmethod
    def get_role_from_display_name(display_name: str) -> Optional[UserRole]:
        """Получить роль из отображаемого имени"""
        SettingsService._get_or_create_default_role_displays()
        
        db_generator = get_db()
        db = next(db_generator)
        
        role_display = db.query(RoleDisplay).filter(RoleDisplay.display_name == display_name).first()
        if role_display:
            return role_display.role
        return None
    
    @staticmethod
    def update_role_display(role: UserRole, new_display_name: str) -> bool:
        """Обновить отображаемое имя роли"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            role_display = db.query(RoleDisplay).filter(RoleDisplay.role == role).first()
            if role_display:
                role_display.display_name = new_display_name
            else:
                role_display = RoleDisplay(role=role, display_name=new_display_name)
                db.add(role_display)
            
            db.commit()
            logger.info(f"Обновлено отображение роли {role}: {new_display_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении отображения роли: {e}")
            return False
    
    @staticmethod
    def add_district(district_name: str) -> bool:
        """Добавление нового района"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Проверяем, не существует ли уже такой район
            existing = db.query(District).filter(District.name == district_name).first()
            if existing:
                if not existing.is_active:
                    # Реактивируем неактивный район
                    existing.is_active = True
                    db.commit()
                    logger.info(f"Реактивирован район: {district_name}")
                    return True
                else:
                    logger.warning(f"Район {district_name} уже существует")
                    return False
            
            # Создаем новый район
            district = District(name=district_name, is_active=True)
            db.add(district)
            db.commit()
            
            logger.info(f"Добавлен новый район: {district_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении района: {e}")
            return False
    
    @staticmethod
    def remove_district(district_name: str) -> bool:
        """Деактивация района"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            district = db.query(District).filter(District.name == district_name).first()
            if not district:
                logger.warning(f"Район {district_name} не найден")
                return False
            
            district.is_active = False
            db.commit()
            
            logger.info(f"Район {district_name} деактивирован")
            return True
        except Exception as e:
            logger.error(f"Ошибка при деактивации района: {e}")
            return False
    
    @staticmethod
    def get_game_rules() -> str:
        """Получение активных правил игры"""
        db_generator = get_db()
        db = next(db_generator)
        
        rule = db.query(GameRule).filter(GameRule.is_active == True).order_by(GameRule.version.desc()).first()
        return rule.content if rule else "Правила не найдены"
    
    @staticmethod
    def update_game_rules(new_rules: str) -> bool:
        """Обновление правил игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Деактивируем старые правила
            db.query(GameRule).update({GameRule.is_active: False})
            
            # Получаем номер последней версии
            last_version = db.query(GameRule).order_by(GameRule.version.desc()).first()
            new_version = (last_version.version + 1) if last_version else 1
            
            # Создаем новые правила
            new_rule = GameRule(content=new_rules, version=new_version, is_active=True)
            db.add(new_rule)
            db.commit()
            
            logger.info(f"Правила игры обновлены до версии {new_version}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении правил: {e}")
            return False
    
    @staticmethod
    def add_role(role_name: str, description: Optional[str] = None) -> bool:
        """Добавление новой роли"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Проверяем, не существует ли уже такая роль
            existing = db.query(Role).filter(Role.name == role_name).first()
            if existing:
                if not existing.is_active:
                    # Реактивируем неактивную роль
                    existing.is_active = True
                    existing.description = description
                    db.commit()
                    logger.info(f"Реактивирована роль: {role_name}")
                    return True
                else:
                    logger.warning(f"Роль {role_name} уже существует")
                    return False
            
            # Создаем новую роль
            role = Role(name=role_name, description=description, is_active=True)
            db.add(role)
            db.commit()
            
            logger.info(f"Добавлена новая роль: {role_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении роли: {e}")
            return False
    
    @staticmethod
    def remove_role(role_name: str) -> bool:
        """Деактивация роли"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                logger.warning(f"Роль {role_name} не найдена")
                return False
            
            role.is_active = False
            db.commit()
            
            logger.info(f"Роль {role_name} деактивирована")
            return True
        except Exception as e:
            logger.error(f"Ошибка при деактивации роли: {e}")
            return False 