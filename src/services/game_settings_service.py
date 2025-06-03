from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from src.models.base import get_db
from src.models.settings import GameSettings

class GameSettingsService:
    """Сервис для работы с настройками игры"""
    
    @staticmethod
    def get_settings() -> GameSettings:
        """Получить текущие настройки игры"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            settings = db.query(GameSettings).first()
            
            # Если настроек еще нет, создаем дефолтные
            if not settings:
                settings = GameSettings()
                db.add(settings)
                db.commit()
                db.refresh(settings)
                logger.info("Созданы дефолтные настройки игры")
            
            return settings
            
        except Exception as e:
            logger.error(f"Ошибка получения настроек игры: {e}")
            # Возвращаем дефолтные настройки в случае ошибки
            return GameSettings()
        finally:
            db.close()
    
    @staticmethod
    def update_settings(**kwargs) -> bool:
        """Обновить настройки игры"""
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            settings = db.query(GameSettings).first()
            
            # Если настроек еще нет, создаем новые
            if not settings:
                settings = GameSettings()
                db.add(settings)
            
            # Обновляем только переданные параметры
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
                    logger.debug(f"Обновлена настройка {key}: {value}")
            
            db.commit()
            logger.info(f"Настройки игры обновлены: {kwargs}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления настроек игры: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    @staticmethod
    def is_auto_mode_enabled() -> bool:
        """Проверить, включен ли автоматический режим"""
        settings = GameSettingsService.get_settings()
        return not settings.manual_control_mode
    
    @staticmethod
    def is_manual_control_mode() -> bool:
        """Проверить, включен ли режим ручного управления"""
        settings = GameSettingsService.get_settings()
        return settings.manual_control_mode
    
    @staticmethod
    def get_hiding_phase_duration() -> int:
        """Получить длительность фазы пряток в минутах"""
        settings = GameSettingsService.get_settings()
        return settings.hiding_phase_duration
    
    @staticmethod
    def get_searching_phase_duration() -> int:
        """Получить длительность фазы поиска в минутах"""
        settings = GameSettingsService.get_settings()
        return settings.searching_phase_duration
    
    @staticmethod
    def should_auto_start_game() -> bool:
        """Проверить, нужно ли автоматически стартовать игру"""
        settings = GameSettingsService.get_settings()
        return settings.auto_start_game and not settings.manual_control_mode
    
    @staticmethod
    def should_auto_assign_roles() -> bool:
        """Проверить, нужно ли автоматически распределять роли"""
        settings = GameSettingsService.get_settings()
        return settings.auto_assign_roles and not settings.manual_control_mode
    
    @staticmethod
    def should_auto_start_hiding() -> bool:
        """Проверить, нужно ли автоматически стартовать фазу пряток"""
        settings = GameSettingsService.get_settings()
        return settings.auto_start_hiding and not settings.manual_control_mode
    
    @staticmethod
    def should_auto_start_searching() -> bool:
        """Проверить, нужно ли автоматически стартовать фазу поиска"""
        settings = GameSettingsService.get_settings()
        return settings.auto_start_searching and not settings.manual_control_mode
    
    @staticmethod
    def should_auto_end_game() -> bool:
        """Проверить, нужно ли автоматически завершать игру"""
        settings = GameSettingsService.get_settings()
        return settings.auto_end_game and not settings.manual_control_mode
    
    @staticmethod
    def get_min_participants_to_start() -> int:
        """Получить минимальное количество участников для старта"""
        settings = GameSettingsService.get_settings()
        return settings.min_participants_to_start
    
    @staticmethod
    def enable_manual_control_mode() -> bool:
        """Включить режим ручного управления"""
        return GameSettingsService.update_settings(manual_control_mode=True)
    
    @staticmethod
    def disable_manual_control_mode() -> bool:
        """Отключить режим ручного управления"""
        return GameSettingsService.update_settings(manual_control_mode=False)
    
    @staticmethod
    def get_settings_summary() -> Dict[str, Any]:
        """Получить краткую сводку настроек"""
        settings = GameSettingsService.get_settings()
        
        return {
            "manual_control_mode": settings.manual_control_mode,
            "auto_start_game": settings.auto_start_game,
            "auto_start_hiding": settings.auto_start_hiding,
            "auto_start_searching": settings.auto_start_searching,
            "auto_assign_roles": settings.auto_assign_roles,
            "auto_end_game": settings.auto_end_game,
            "hiding_phase_duration": settings.hiding_phase_duration,
            "searching_phase_duration": settings.searching_phase_duration,
            "min_participants_to_start": settings.min_participants_to_start,
            "allow_early_start": settings.allow_early_start
        }
    
    @staticmethod
    def reset_to_defaults() -> bool:
        """Сбросить настройки к значениям по умолчанию"""
        default_settings = {
            "auto_start_game": True,
            "auto_start_hiding": True,
            "auto_start_searching": True,
            "auto_assign_roles": True,
            "auto_end_game": True,
            "hiding_phase_duration": 15,
            "searching_phase_duration": 60,
            "game_start_notification_time": 10,
            "manual_control_mode": False,
            "require_admin_approval": False,
            "notify_on_role_assignment": True,
            "notify_on_phase_change": True,
            "notify_on_participant_action": True,
            "allow_early_start": True,
            "min_participants_to_start": 3
        }
        
        return GameSettingsService.update_settings(**default_settings)