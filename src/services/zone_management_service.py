from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from loguru import logger

from src.models.base import get_db
from src.models.settings import District, DistrictZone
from src.services.location_service import LocationService

class ZoneManagementService:
    """Сервис для управления зонами районов"""
    
    @staticmethod
    def create_district_zone(
        district_name: str,
        zone_name: str,
        center_lat: float,
        center_lon: float,
        radius: int,
        description: str = None,
        is_default: bool = False
    ) -> Optional[DistrictZone]:
        """Создать новую зону для района"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Проверяем существование района
            district = db.query(District).filter(District.name == district_name).first()
            if not district:
                logger.error(f"Район {district_name} не существует")
                return None
            
            # Если создаём зону по умолчанию, снимаем флаг с других зон
            if is_default:
                existing_default = db.query(DistrictZone).filter(
                    DistrictZone.district_name == district_name,
                    DistrictZone.is_default == True
                ).first()
                if existing_default:
                    existing_default.is_default = False
            
            # Создаём новую зону
            zone = DistrictZone(
                district_name=district_name,
                zone_name=zone_name,
                center_lat=center_lat,
                center_lon=center_lon,
                radius=radius,
                description=description,
                is_default=is_default,
                is_active=True
            )
            
            db.add(zone)
            db.commit()
            db.refresh(zone)
            
            logger.info(f"Создана зона {zone_name} для района {district_name}")
            return zone
            
        except Exception as e:
            logger.error(f"Ошибка создания зоны: {e}")
            return None
        


    @staticmethod
    def get_zone_by_id(zone_id:int) -> Optional[DistrictZone]:
        try:
            db_generator = get_db()
            db = next(db_generator)
            zone = db.query(DistrictZone).filter(DistrictZone.id == zone_id).first()
            return zone
        except Exception as e:
            logger.error(f"Ошибка получения зоны по ID: {e}")
            return None
        


    
    @staticmethod
    def get_district_zones_info(district_name: str) -> List[dict]:
        """Получить информацию о всех зонах района"""
        try:
            zones = LocationService.get_district_zones(district_name)
            
            zones_info = []
            for zone in zones:
                info = {
                    "id": zone.id,
                    "zone_name": zone.zone_name,
                    "center_lat": zone.center_lat,
                    "center_lon": zone.center_lon,
                    "radius": zone.radius,
                    "area_km2": zone.area_km2,
                    "is_default": zone.is_default,
                    "is_active": zone.is_active,
                    "description": zone.description,
                    "created_at": zone.created_at
                }
                zones_info.append(info)
            
            return zones_info
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о зонах: {e}")
            return []
    
    @staticmethod
    def update_district_zone(
        zone_id: int,
        zone_name: str = None,
        center_lat: float = None,
        center_lon: float = None,
        radius: int = None,
        description: str = None,
        is_default: bool = None,
        is_active: bool = None
    ) -> bool:
        """Обновить зону района"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            zone = db.query(DistrictZone).filter(DistrictZone.id == zone_id).first()
            if not zone:
                logger.error(f"Зона с ID {zone_id} не найдена")
                return False
            
            # Если устанавливаем как зону по умолчанию, снимаем флаг с других
            if is_default is True:
                existing_default = db.query(DistrictZone).filter(
                    DistrictZone.district_name == zone.district_name,
                    DistrictZone.is_default == True,
                    DistrictZone.id != zone_id
                ).first()
                if existing_default:
                    existing_default.is_default = False
            
            # Обновляем поля
            if zone_name is not None:
                zone.zone_name = zone_name
            if center_lat is not None:
                zone.center_lat = center_lat
            if center_lon is not None:
                zone.center_lon = center_lon
            if radius is not None:
                zone.radius = radius
            if description is not None:
                zone.description = description
            if is_default is not None:
                zone.is_default = is_default
            if is_active is not None:
                zone.is_active = is_active
            
            db.commit()
            logger.info(f"Зона {zone.zone_name} обновлена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления зоны: {e}")
            return False
    
    @staticmethod
    def delete_district_zone(zone_id: int) -> bool:
        """Удалить зону района"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            zone = db.query(DistrictZone).filter(DistrictZone.id == zone_id).first()
            if not zone:
                logger.error(f"Зона с ID {zone_id} не найдена")
                return False
            
            zone_name = zone.zone_name
            district_name = zone.district_name
            
            db.delete(zone)
            db.commit()
            
            logger.info(f"Зона {zone_name} района {district_name} удалена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления зоны: {e}")
            return False
    
    @staticmethod
    def test_point_in_zones(lat: float, lon: float, district_name: str) -> List[dict]:
        """Проверить, в какие зоны попадает точка"""
        try:
            zones = LocationService.get_district_zones(district_name)
            
            results = []
            for zone in zones:
                is_in_zone = LocationService.is_point_in_zone(lat, lon, zone)
                distance = LocationService.calculate_distance(
                    lat, lon, zone.center_lat, zone.center_lon
                )
                
                result = {
                    "zone_name": zone.zone_name,
                    "is_in_zone": is_in_zone,
                    "distance_m": round(distance),
                    "zone_radius": zone.radius
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка тестирования точки: {e}")
            return []
    
    @staticmethod
    def create_default_zones_for_district(district_name: str) -> bool:
        """Создать зоны по умолчанию для района"""
        try:
            # Проверяем, есть ли уже зоны
            existing_zones = LocationService.get_district_zones(district_name)
            if existing_zones:
                logger.info(f"У района {district_name} уже есть зоны")
                return False
            
            # Создаём базовую зону (нужно будет настроить координаты)
            default_zone = ZoneManagementService.create_district_zone(
                district_name=district_name,
                zone_name="Центральная зона",
                center_lat=55.7558,  # Примерные координаты (Москва)
                center_lon=37.6176,
                radius=1000,  # 1 км
                description="Зона по умолчанию для района. Необходимо настроить координаты.",
                is_default=True
            )
            
            if default_zone:
                logger.info(f"Создана зона по умолчанию для района {district_name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка создания зон по умолчанию: {e}")
            return False 