from datetime import datetime
from typing import Optional, List
from loguru import logger

from src.models.base import get_db
from src.models.game import Photo


class PhotoService:
    """Сервис для работы с фотографиями"""
    
    @staticmethod
    def save_user_photo(user_id: int, game_id: int, file_id: str) -> bool:
        """Сохранить фотографию пользователя для игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Создаем новую запись фотографии
            photo = Photo(
                user_id=user_id,
                game_id=game_id,
                file_id=file_id,
                is_approved=None
            )
            
            db.add(photo)
            db.commit()
            
            logger.info(f"Сохранена фотография пользователя {user_id} для игры {game_id}: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения фотографии: {e}")
            return False
    
    @staticmethod
    def approve_photo(file_id: str, approver_id: int) -> bool:
        """Подтвердить фотографию"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photo = db.query(Photo).filter(Photo.file_id == file_id).first()
            if not photo:
                logger.error(f"Фотография с file_id {file_id} не найдена")
                return False
            
            photo.is_approved = True
            
            db.commit()
            
            logger.info(f"Фотография {file_id} подтверждена пользователем {approver_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подтверждения фотографии: {e}")
            return False
    
    @staticmethod
    def reject_photo(file_id: str, reviewer_id: int) -> bool:
        """Отклонить фотографию"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photo = db.query(Photo).filter(Photo.file_id == file_id).first()
            if not photo:
                logger.error(f"Фотография с file_id {file_id} не найдена")
                return False
            
            photo.is_approved = False
            
            db.commit()
            
            logger.info(f"Фотография {file_id} отклонена пользователем {reviewer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отклонения фотографии: {e}")
            return False
    
    @staticmethod
    def get_photo_seeker_id(file_id: str) -> Optional[int]:
        """Получить ID искателя по фотографии"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photo = db.query(Photo).filter(Photo.file_id == file_id).first()
            if photo:
                return photo.user_id
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения ID искателя: {e}")
            return None
    
    @staticmethod
    def get_game_photos(game_id: int) -> List[Photo]:
        """Получить все фотографии для игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photos = db.query(Photo).filter(
                Photo.game_id == game_id
            ).order_by(Photo.created_at.desc()).all()
            
            return photos
            
        except Exception as e:
            logger.error(f"Ошибка получения фотографий игры: {e}")
            return []
    
    @staticmethod
    def get_user_photos(user_id: int, game_id: int) -> List[Photo]:
        """Получить фотографии пользователя в конкретной игре"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photos = db.query(Photo).filter(
                Photo.user_id == user_id,
                Photo.game_id == game_id
            ).order_by(Photo.created_at.desc()).all()
            
            return photos
            
        except Exception as e:
            logger.error(f"Ошибка получения фотографий пользователя: {e}")
            return []
    
    @staticmethod
    def get_pending_photos(game_id: int) -> List[Photo]:
        """Получить фотографии, ожидающие проверки"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photos = db.query(Photo).filter(
                Photo.game_id == game_id,
                Photo.is_approved == None
            ).order_by(Photo.created_at.asc()).all()
            
            return photos
            
        except Exception as e:
            logger.error(f"Ошибка получения ожидающих фотографий: {e}")
            return []
    
    @staticmethod
    def count_approved_photos(user_id: int, game_id: int) -> int:
        """Подсчитать количество подтвержденных фотографий пользователя в игре"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            count = db.query(Photo).filter(
                Photo.user_id == user_id,
                Photo.game_id == game_id,
                Photo.is_approved == True
            ).count()
            
            return count
            
        except Exception as e:
            logger.error(f"Ошибка подсчета подтвержденных фотографий: {e}")
            return 0
    
    @staticmethod
    def delete_photo(file_id: str) -> bool:
        """Удалить фотографию"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photo = db.query(Photo).filter(Photo.file_id == file_id).first()
            if not photo:
                logger.error(f"Фотография с file_id {file_id} не найдена")
                return False
            
            db.delete(photo)
            db.commit()
            
            logger.info(f"Фотография {file_id} удалена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления фотографии: {e}")
            return False 