from datetime import datetime
from typing import List, Tuple, Optional
from loguru import logger
import math

from src.models.base import get_db
from src.models.game import Location, Game
from src.models.user import User
from src.models.settings import DistrictZone


class LocationService:
    """Сервис для работы с геолокацией"""
    
    @staticmethod
    def save_user_location(user_id: int, game_id: int, latitude: float, longitude: float) -> bool:
        """Сохранить геолокацию пользователя для игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Создаем новую запись геолокации
            location = Location(
                user_id=user_id,
                game_id=game_id,
                latitude=latitude,
                longitude=longitude
            )
            
            db.add(location)
            db.commit()
            
            logger.info(f"Сохранена геолокация пользователя {user_id} для игры {game_id}: {latitude}, {longitude}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения геолокации: {e}")
            return False
    
    @staticmethod
    def get_user_latest_location(user_id: int, game_id: int) -> Optional[Location]:
        """Получить последнюю геолокацию пользователя для игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            location = db.query(Location).filter(
                Location.user_id == user_id,
                Location.game_id == game_id
            ).order_by(Location.timestamp.desc()).first()
            
            return location
            
        except Exception as e:
            logger.error(f"Ошибка получения геолокации: {e}")
            return None
    
    @staticmethod
    def get_game_participants_locations(game_id: int) -> List[Tuple[User, Location]]:
        """Получить последние геолокации всех участников игры"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Получаем последние геолокации для каждого участника
            result = []
            
            # Подзапрос для получения последних геолокаций
            latest_locations = db.query(
                Location.user_id,
                db.func.max(Location.timestamp).label('latest_time')
            ).filter(
                Location.game_id == game_id
            ).group_by(Location.user_id).subquery()
            
            # Основной запрос с джойном
            participants = db.query(User, Location).join(
                Location, User.id == Location.user_id
            ).join(
                latest_locations,
                (Location.user_id == latest_locations.c.user_id) &
                (Location.timestamp == latest_locations.c.latest_time)
            ).filter(
                Location.game_id == game_id
            ).all()
            
            return participants
            
        except Exception as e:
            logger.error(f"Ошибка получения геолокаций участников: {e}")
            return []
    
    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Вычислить расстояние между двумя точками в метрах (формула гаверсинуса)"""
        # Радиус Земли в метрах
        R = 6371000
        
        # Преобразуем градусы в радианы
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        # Формула гаверсинуса
        a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) * math.sin(delta_lon / 2))
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance
    
    @staticmethod
    def is_user_in_game_zone(user_id: int, game_id: int, zone_radius: int = None) -> bool:
        """Проверить, находится ли пользователь в игровой зоне"""
        try:
            # Получаем последнюю геолокацию пользователя
            user_location = LocationService.get_user_latest_location(user_id, game_id)
            if not user_location:
                return False
            
            # Получаем игру
            db_generator = get_db()
            db = next(db_generator)
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return False
            
            # Если у игры есть собственная зона - используем её
            if game.has_game_zone:
                distance = LocationService.calculate_distance(
                    user_location.latitude,
                    user_location.longitude,
                    game.zone_center_lat,
                    game.zone_center_lon
                )
                return distance <= game.zone_radius
            
            # Если передан параметр zone_radius - используем его с центром по умолчанию
            if zone_radius is not None:
                # Пробуем получить зону района по умолчанию
                default_zone = LocationService.get_default_district_zone(game.district)
                if default_zone:
                    distance = LocationService.calculate_distance(
                        user_location.latitude,
                        user_location.longitude,
                        default_zone.center_lat,
                        default_zone.center_lon
                    )
                    return distance <= zone_radius
                else:
                    # Fallback: используем первого участника как центр
                    first_location = db.query(Location).filter(
                        Location.game_id == game_id
                    ).order_by(Location.timestamp.asc()).first()
                    
                    if not first_location:
                        return True  # Если нет других участников, считаем что в зоне
                    
                    distance = LocationService.calculate_distance(
                        user_location.latitude,
                        user_location.longitude,
                        first_location.latitude,
                        first_location.longitude
                    )
                    return distance <= zone_radius
            
            # Если ни зоны игры, ни параметра нет - считаем что в зоне
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки нахождения в игровой зоне: {e}")
            return False
    
    @staticmethod
    def get_nearby_users(user_id: int, game_id: int, radius: int = 100) -> List[Tuple[User, Location, float]]:
        """Получить список ближайших пользователей в радиусе"""
        try:
            user_location = LocationService.get_user_latest_location(user_id, game_id)
            if not user_location:
                return []
            
            participants = LocationService.get_game_participants_locations(game_id)
            nearby_users = []
            
            for participant_user, participant_location in participants:
                if participant_user.id == user_id:
                    continue
                
                distance = LocationService.calculate_distance(
                    user_location.latitude,
                    user_location.longitude,
                    participant_location.latitude,
                    participant_location.longitude
                )
                
                if distance <= radius:
                    nearby_users.append((participant_user, participant_location, distance))
            
            # Сортируем по расстоянию
            nearby_users.sort(key=lambda x: x[2])
            return nearby_users
            
        except Exception as e:
            logger.error(f"Ошибка поиска ближайших пользователей: {e}")
            return []
    
    @staticmethod
    def get_district_zones(district_name: str) -> List[DistrictZone]:
        """Получить все активные зоны района"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            zones = db.query(DistrictZone).filter(
                DistrictZone.district_name == district_name,
                DistrictZone.is_active == True
            ).order_by(DistrictZone.zone_name).all()
            
            return zones
            
        except Exception as e:
            logger.error(f"Ошибка получения зон района {district_name}: {e}")
            return []
    
    @staticmethod
    def get_default_district_zone(district_name: str) -> Optional[DistrictZone]:
        """Получить зону района по умолчанию"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Сначала ищем зону по умолчанию
            zone = db.query(DistrictZone).filter(
                DistrictZone.district_name == district_name,
                DistrictZone.is_active == True,
                DistrictZone.is_default == True
            ).first()
            
            # Если зоны по умолчанию нет, берем первую активную
            if not zone:
                zone = db.query(DistrictZone).filter(
                    DistrictZone.district_name == district_name,
                    DistrictZone.is_active == True
                ).first()
            
            return zone
            
        except Exception as e:
            logger.error(f"Ошибка получения зоны по умолчанию для района {district_name}: {e}")
            return None
    
    @staticmethod
    def is_point_in_zone(lat: float, lon: float, zone: DistrictZone) -> bool:
        """Проверить, находится ли точка в зоне"""
        distance = LocationService.calculate_distance(
            lat, lon, zone.center_lat, zone.center_lon
        )
        return distance <= zone.radius
    
    @staticmethod
    def auto_set_game_zone_from_district(game: Game) -> bool:
        """Автоматически установить зону игры из зоны района по умолчанию"""
        try:
            default_zone = LocationService.get_default_district_zone(game.district)
            if not default_zone:
                logger.warning(f"Для района {game.district} не найдена зона по умолчанию")
                return False
            
            game.set_game_zone(
                default_zone.center_lat,
                default_zone.center_lon, 
                default_zone.radius
            )
            
            logger.info(f"Игре {game.id} установлена зона из района {game.district}: {default_zone.zone_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка автоустановки зоны игры: {e}")
            return False 