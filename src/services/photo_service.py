from datetime import datetime
from typing import Optional, List
from loguru import logger

from src.services.game_service import GameService
from src.models.base import get_db
from src.models.game import Photo, PhotoType, GameParticipant, GameRole


class PhotoService:
    """Сервис для работы с фотографиями"""
    
    @staticmethod
    def save_user_photo(user_id: int, game_id: int, file_id: str, photo_type: PhotoType, 
                       description: Optional[str] = None, found_driver_id: Optional[int] = None) -> Optional[Photo]:
        """Сохранить фотографию пользователя для игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Создаем новую запись фотографии
            photo = Photo(
                user_id=user_id,
                game_id=game_id,
                file_id=file_id,
                photo_type=photo_type,
                description=description,
                found_driver_id=found_driver_id,
                is_approved=None  # Ожидает проверки админом
            )
            
            db.add(photo)
            db.commit()
            db.refresh(photo)
            
            
            logger.info(f"Сохранена фотография {photo_type.value} пользователя {user_id} для игры {game_id}: ID={photo.id}")
            return photo
            
        except Exception as e:
            logger.error(f"Ошибка сохранения фотографии: {e}")
            return None
    
    @staticmethod
    def approve_photo(photo_id: int, admin_id: int) -> bool:
        """Подтвердить фотографию (админом)"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photo = db.query(Photo).filter(Photo.id == photo_id).first()
            if not photo:
                logger.error(f"Фотография с ID {photo_id} не найдена")
                return False
            
            photo.is_approved = True
            photo.approved_by = admin_id
            photo.reviewed_at = datetime.now()
            
            # Если это фото найденной машины, отмечаем водителя как найденного
            if photo.photo_type == PhotoType.FOUND_CAR and photo.found_driver_id:
                GameService.mark_participant_found(photo.game_id, photo.found_driver_id)
                
            # Если это фото места пряток от водителя, отмечаем что он спрятался
            if photo.photo_type == PhotoType.HIDING_SPOT:
                GameService.update_participant_hidden_status(photo.game_id, photo.user_id, True)
            
            db.commit()

            
            logger.info(f"Фотография {photo_id} подтверждена админом {admin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подтверждения фотографии: {e}")
            return False
    
    @staticmethod
    def reject_photo(photo_id: int, admin_id: int, reason: Optional[str] = None) -> bool:
        """Отклонить фотографию (админом)"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photo = db.query(Photo).filter(Photo.id == photo_id).first()
            if not photo:
                logger.error(f"Фотография с ID {photo_id} не найдена")
                return False
            
            photo.is_approved = False
            photo.approved_by = admin_id
            photo.reviewed_at = datetime.now()
            if reason:
                photo.description = (photo.description or "") + f"\nОтклонено: {reason}"
            
            db.commit()
            
            logger.info(f"Фотография {photo_id} отклонена админом {admin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отклонения фотографии: {e}")
            return False
    
    @staticmethod
    def get_photo_by_id(photo_id: int) -> Optional[Photo]:
        """Получить фотографию по ID"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photo = db.query(Photo).filter(Photo.id == photo_id).first()
            return photo
            
        except Exception as e:
            logger.error(f"Ошибка получения фотографии по ID: {e}")
            return None
    
    @staticmethod
    def get_game_photos(game_id: int, photo_type: Optional[PhotoType] = None) -> List[Photo]:
        """Получить все фотографии для игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            query = db.query(Photo).filter(Photo.game_id == game_id)
            
            if photo_type:
                query = query.filter(Photo.photo_type == photo_type)
            
            photos = query.order_by(Photo.uploaded_at.desc()).all()
            return photos
            
        except Exception as e:
            logger.error(f"Ошибка получения фотографий игры: {e}")
            return []
    
    @staticmethod
    def get_pending_photos(game_id: Optional[int] = None) -> List[Photo]:
        """Получить фотографии, ожидающие проверки админом"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            query = db.query(Photo).filter(Photo.is_approved == None)
            
            if game_id:
                query = query.filter(Photo.game_id == game_id)
            
            photos = query.order_by(Photo.uploaded_at.asc()).all()
            return photos
            
        except Exception as e:
            logger.error(f"Ошибка получения ожидающих фотографий: {e}")
            return []
    
    @staticmethod
    def get_hiding_photos_stats(game_id: int) -> dict:
        """Получить статистику по фото мест пряток для игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Получаем всех водителей в игре
            drivers = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.role == GameRole.DRIVER
            ).all()
            
            total_drivers = len(drivers)
            hidden_drivers = len([d for d in drivers if d.has_hidden])
            not_hidden_drivers = [d for d in drivers if not d.has_hidden]
            
            # Получаем фото мест пряток
            hiding_photos = db.query(Photo).filter(
                Photo.game_id == game_id,
                Photo.photo_type == PhotoType.HIDING_SPOT
            ).all()
            
            return {
                'total_drivers': total_drivers,
                'hidden_count': hidden_drivers,
                'not_hidden_count': total_drivers - hidden_drivers,
                'not_hidden_drivers': not_hidden_drivers,
                'photos_count': len(hiding_photos),
                'approved_photos': len([p for p in hiding_photos if p.is_approved == True]),
                'pending_photos': len([p for p in hiding_photos if p.is_approved == None]),
                'rejected_photos': len([p for p in hiding_photos if p.is_approved == False])
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики фотографий: {e}")
            return {}
    
    @staticmethod
    def count_approved_photos(user_id: int, game_id: int, photo_type: Optional[PhotoType] = None) -> int:
        """Подсчитать количество подтвержденных фотографий пользователя в игре"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            query = db.query(Photo).filter(
                Photo.user_id == user_id,
                Photo.game_id == game_id,
                Photo.is_approved == True
            )
            
            if photo_type:
                query = query.filter(Photo.photo_type == photo_type)
            
            count = query.count()
            return count
            
        except Exception as e:
            logger.error(f"Ошибка подсчета подтвержденных фотографий: {e}")
            return 0
    
    @staticmethod
    def delete_photo(photo_id: int) -> bool:
        """Удалить фотографию"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            photo = db.query(Photo).filter(Photo.id == photo_id).first()
            if not photo:
                logger.error(f"Фотография с ID {photo_id} не найдена")
                return False
            
            db.delete(photo)
            db.commit()
            
            logger.info(f"Фотография {photo_id} удалена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления фотографии: {e}")
            return False
    
    @staticmethod
    def get_user_photos(user_id: int, game_id: int, photo_type: Optional[PhotoType] = None) -> List[Photo]:
        """Получить фотографии пользователя в конкретной игре"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            query = db.query(Photo).filter(
                Photo.user_id == user_id,
                Photo.game_id == game_id
            )
            
            if photo_type:
                query = query.filter(Photo.photo_type == photo_type)
            
            photos = query.order_by(Photo.uploaded_at.desc()).all()
            return photos
            
        except Exception as e:
            logger.error(f"Ошибка получения фотографий пользователя: {e}")
            return [] 