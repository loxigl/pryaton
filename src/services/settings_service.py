from sqlalchemy.orm import Session
from typing import List, Optional
import json
import os
from loguru import logger

from src.models.base import get_db
from src.models.settings import District, Role, GameRule

class SettingsService:
    """Сервис для управления настройками системы"""
    
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
    def _get_or_create_default_roles() -> None:
        """Создает дефолтные роли если их нет в БД"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Проверяем есть ли роли в БД
        if db.query(Role).count() == 0:
            default_roles = ["Игрок", "Водитель", "Наблюдатель"]
            
            for role_name in default_roles:
                role = Role(name=role_name, is_active=True)
                db.add(role)
            
            db.commit()
            logger.info(f"Созданы дефолтные роли: {len(default_roles)} шт.")
    
    @staticmethod
    def _get_or_create_default_rules() -> None:
        """Создает дефолтные правила если их нет в БД"""
        db_generator = get_db()
        db = next(db_generator)
        
        # Проверяем есть ли правила в БД
        if db.query(GameRule).filter(GameRule.is_active == True).count() == 0:
            default_rules = """
🎮 <b>Правила игры PRYATON</b>

<b>Описание игры:</b>
PRYATON - это игра в прятки на автомобилях, где один или несколько игроков (водители) прячутся в выбранном районе, а остальные участники (искатели) пытаются их найти.

<b>Правила для водителей:</b>
• Вы получите роль водителя случайным образом или по назначению администратора
• Ваша задача - спрятаться в выбранном районе и оставаться незамеченными
• Время на прятки - 30 минут с момента начала игры
• Вы должны оставаться в пределах выбранного района
• При обнаружении честно сообщить об этом

<b>Правила для искателей:</b>
• Ваша задача - найти спрятавшихся водителей
• Вы можете перемещаться по району на автомобиле
• При обнаружении сделайте фото автомобиля и отправьте его в бот
• Запрещено выходить из автомобиля для поиска

<b>Общие правила:</b>
• Соблюдайте ПДД и будьте внимательны на дороге
• Игра проводится только на автомобилях
• Запрещено создавать опасные ситуации
• Уважайте других участников и прохожих
• В случае споров решение принимает администратор

<b>Ответственность:</b>
Участвуя в игре, вы берете на себя полную ответственность за свои действия и возможные последствия. Организаторы не несут ответственности за любые происшествия.

Нажимая "Да, согласен с правилами", вы подтверждаете, что прочитали и согласны с правилами игры.
            """
            
            rule = GameRule(content=default_rules.strip(), version=1, is_active=True)
            db.add(rule)
            db.commit()
            logger.info("Созданы дефолтные правила игры")
    
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
        """Получение списка активных ролей"""
        SettingsService._get_or_create_default_roles()
        
        db_generator = get_db()
        db = next(db_generator)
        
        roles = db.query(Role).filter(Role.is_active == True).order_by(Role.name).all()
        return [role.name for role in roles]
    
    @staticmethod
    def get_all_roles() -> List[Role]:
        """Получение всех ролей (включая неактивные)"""
        SettingsService._get_or_create_default_roles()
        
        db_generator = get_db()
        db = next(db_generator)
        
        return db.query(Role).order_by(Role.name).all()
    
    @staticmethod
    def get_game_rules() -> str:
        """Получение активных правил игры"""
        SettingsService._get_or_create_default_rules()
        
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
    def add_district(district_name: str, description: Optional[str] = None) -> bool:
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
                    existing.description = description
                    db.commit()
                    logger.info(f"Реактивирован район: {district_name}")
                    return True
                else:
                    logger.warning(f"Район {district_name} уже существует")
                    return False
            
            # Создаем новый район
            district = District(name=district_name, description=description, is_active=True)
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