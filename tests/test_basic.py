import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Импорты сервисов для тестирования
from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.location_service import LocationService
from src.services.photo_service import PhotoService
from src.services.settings_service import SettingsService
from src.services.scheduler_service import SchedulerService
from src.services.monitoring_service import MonitoringService

# Импорты моделей
from src.models.user import User, UserRole
from src.models.game import Game, GameStatus, GameParticipant, GameRole


class TestUserService:
    """Тесты для UserService"""
    
    def test_is_admin_with_valid_id(self):
        """Тест проверки админ прав с валидным ID"""
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = "123456789,987654321"
            
            assert UserService.is_admin(123456789) is True
            assert UserService.is_admin(987654321) is True
            assert UserService.is_admin(111111111) is False
    
    def test_is_admin_with_empty_config(self):
        """Тест проверки админ прав с пустой конфигурацией"""
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = ""
            
            assert UserService.is_admin(123456789) is False


class TestGameService:
    """Тесты для GameService"""
    
    @patch('src.services.game_service.get_db')
    def test_create_game_validation(self, mock_get_db):
        """Тест валидации при создании игры"""
        # Проверяем что количество водителей не может быть >= общего количества участников
        with pytest.raises(ValueError, match="Количество водителей не может быть больше"):
            GameService.create_game(
                district="Тестовый район",
                max_participants=2,
                scheduled_at=datetime.now() + timedelta(hours=1),
                creator_id=1,
                max_drivers=2  # Равно max_participants
            )
        
        with pytest.raises(ValueError, match="Количество водителей не может быть больше"):
            GameService.create_game(
                district="Тестовый район",
                max_participants=2,
                scheduled_at=datetime.now() + timedelta(hours=1),
                creator_id=1,
                max_drivers=3  # Больше max_participants
            )


class TestLocationService:
    """Тесты для LocationService"""
    
    def test_calculate_distance(self):
        """Тест вычисления расстояния между точками"""
        # Тест расстояния между известными точками
        # Москва - Красная площадь и Московский Кремль (примерно 500 метров)
        lat1, lon1 = 55.7558, 37.6176  # Красная площадь
        lat2, lon2 = 55.7520, 37.6175  # Кремль
        
        distance = LocationService.calculate_distance(lat1, lon1, lat2, lon2)
        
        # Расстояние должно быть около 400-600 метров
        assert 300 <= distance <= 700
    
    def test_calculate_distance_same_point(self):
        """Тест вычисления расстояния для одной точки"""
        lat, lon = 55.7558, 37.6176
        
        distance = LocationService.calculate_distance(lat, lon, lat, lon)
        
        # Расстояние до самой себя должно быть 0
        assert distance == 0


class TestSettingsService:
    """Тесты для SettingsService"""
    
    @patch('src.services.settings_service.get_db')
    def test_get_districts_default(self, mock_get_db):
        """Тест получения дефолтных районов"""
        # Мокаем пустую базу данных
        mock_db = Mock()
        mock_db.query().count.return_value = 0
        mock_get_db.return_value = iter([mock_db])
        
        districts = SettingsService.get_districts()
        
        # Должны вернуться дефолтные районы
        assert len(districts) > 0
        assert "Тестовый район" in districts
    
    @patch('src.services.settings_service.get_db')
    def test_get_available_roles(self, mock_get_db):
        """Тест получения доступных ролей"""
        # Мокаем пустую базу данных
        mock_db = Mock()
        mock_db.query().count.return_value = 0
        mock_get_db.return_value = iter([mock_db])
        
        roles = SettingsService.get_available_roles()
        
        # Должны вернуться все роли с их отображением
        assert len(roles) == 3
        assert "🔍 Игрок" in roles
        assert "🚗 Водитель" in roles
        assert "👁 Наблюдатель" in roles
    
    @patch('src.services.settings_service.get_db')
    def test_get_role_display_name(self, mock_get_db):
        """Тест получения отображаемого имени роли"""
        from src.models.user import UserRole
        
        # Мокаем базу данных с отображениями ролей
        mock_db = Mock()
        mock_role_display = Mock()
        mock_role_display.display_name = "🔍 Игрок"
        mock_db.query().filter().first.return_value = mock_role_display
        mock_get_db.return_value = iter([mock_db])
        
        # Проверяем получение отображения из БД
        assert SettingsService.get_role_display_name(UserRole.PLAYER) == "🔍 Игрок"
        
        # Проверяем получение дефолтного отображения
        mock_db.query().filter().first.return_value = None
        assert SettingsService.get_role_display_name(UserRole.DRIVER) == "🚗 Водитель"
    
    @patch('src.services.settings_service.get_db')
    def test_get_role_from_display_name(self, mock_get_db):
        """Тест получения роли из отображаемого имени"""
        from src.models.user import UserRole
        
        # Мокаем базу данных с отображениями ролей
        mock_db = Mock()
        mock_role_display = Mock()
        mock_role_display.role = UserRole.PLAYER
        mock_db.query().filter().first.return_value = mock_role_display
        mock_get_db.return_value = iter([mock_db])
        
        # Проверяем получение роли из БД
        assert SettingsService.get_role_from_display_name("🔍 Игрок") == UserRole.PLAYER
        
        # Проверяем получение None для несуществующего отображения
        mock_db.query().filter().first.return_value = None
        assert SettingsService.get_role_from_display_name("Несуществующая роль") is None
    
    @patch('src.services.settings_service.get_db')
    def test_update_role_display(self, mock_get_db):
        """Тест обновления отображения роли"""
        from src.models.user import UserRole
        
        # Мокаем базу данных
        mock_db = Mock()
        mock_role_display = Mock()
        mock_db.query().filter().first.return_value = mock_role_display
        mock_get_db.return_value = iter([mock_db])
        
        # Проверяем обновление существующего отображения
        assert SettingsService.update_role_display(UserRole.PLAYER, "🎮 Игрок") is True
        assert mock_role_display.display_name == "🎮 Игрок"
        
        # Проверяем создание нового отображения
        mock_db.query().filter().first.return_value = None
        assert SettingsService.update_role_display(UserRole.DRIVER, "🚘 Водитель") is True
        mock_db.add.assert_called_once()


class TestSchedulerService:
    """Тесты для SchedulerService"""
    
    def test_scheduler_initialization(self):
        """Тест инициализации планировщика"""
        mock_application = Mock()
        mock_application.bot = Mock()
        
        scheduler = SchedulerService(mock_application)
        
        assert scheduler.application == mock_application
        assert scheduler.bot == mock_application.bot
        assert scheduler.hiding_time == 30  # Дефолтное значение
        assert 60 in scheduler.reminder_times  # Дефолтное значение
    
    def test_scheduler_start_stop(self):
        """Тест запуска и остановки планировщика"""
        mock_application = Mock()
        mock_application.bot = Mock()
        
        scheduler = SchedulerService(mock_application)
        
        # Тест запуска
        scheduler.start()
        assert scheduler.scheduler.running is True
        
        # Тест остановки
        scheduler.shutdown()
        assert scheduler.scheduler.running is False


class TestMonitoringService:
    """Тесты для MonitoringService"""
    
    @patch('src.services.monitoring_service.get_db')
    def test_get_active_games_stats_empty(self, mock_get_db):
        """Тест получения статистики при отсутствии игр"""
        mock_db = Mock()
        mock_db.query().filter().count.return_value = 0
        mock_db.query().filter().all.return_value = []
        mock_db.query().count.return_value = 0
        mock_db.query().distinct().count.return_value = 0
        mock_get_db.return_value = iter([mock_db])
        
        stats = MonitoringService.get_active_games_stats()
        
        assert stats.get('active_games_count', 0) == 0
        assert stats.get('today_games_count', 0) == 0
        assert stats.get('total_participants', 0) == 0


@pytest.mark.asyncio
class TestAsyncFunctions:
    """Тесты для асинхронных функций"""
    
    async def test_scheduler_reminder_validation(self):
        """Тест валидации напоминаний планировщика"""
        mock_application = Mock()
        mock_application.bot = Mock()
        
        scheduler = SchedulerService(mock_application)
        
        # Тест что метод существует и может быть вызван
        assert hasattr(scheduler, 'send_game_reminder')
        assert asyncio.iscoroutinefunction(scheduler.send_game_reminder)


class TestIntegration:
    """Интеграционные тесты"""
    
    def test_services_exist(self):
        """Тест что все основные сервисы доступны"""
        services = [
            UserService,
            GameService,
            LocationService,
            PhotoService,
            SettingsService,
            MonitoringService
        ]
        
        for service in services:
            assert service is not None
            assert hasattr(service, '__name__')
    
    def test_user_roles_enum(self):
        """Тест что enum ролей пользователей работает корректно"""
        assert UserRole.PLAYER is not None
        assert UserRole.DRIVER is not None
        assert UserRole.OBSERVER is not None
        
        # Проверяем что можно получить значения
        assert UserRole.PLAYER.value is not None
    
    def test_game_status_enum(self):
        """Тест что enum статусов игр работает корректно"""
        assert GameStatus.RECRUITING is not None
        assert GameStatus.UPCOMING is not None
        assert GameStatus.HIDING_PHASE is not None
        assert GameStatus.COMPLETED is not None
        assert GameStatus.CANCELED is not None
        
        # Проверяем что можно получить значения
        assert GameStatus.RECRUITING.value is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 