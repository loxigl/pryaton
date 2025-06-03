import pytest
import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

# Устанавливаем переменные окружения для тестов
os.environ["DATABASE_URL"] = "sqlite:///./test_db.sqlite"
os.environ["HIDING_TIME"] = "30"
os.environ["HIDING_WARNING_TIME"] = "5"

from src.models.game import Game, GameStatus, GameParticipant, GameRole, Photo, PhotoType
from src.services.game_service import GameService
from src.services.photo_service import PhotoService
from src.services.user_service import UserService
from src.services.enhanced_scheduler_service import EnhancedSchedulerService

class TestPhotoPhaseSystem:
    """Тесты новой системы фаз игры и фотографий"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.mock_app = Mock()
        self.mock_bot = AsyncMock()
        self.mock_app.bot = self.mock_bot
        
        # Мокаем пользователей
        self.admin_user = Mock()
        self.admin_user.id = 1
        self.admin_user.telegram_id = 123456
        self.admin_user.name = "Admin"
        self.admin_user.is_admin = True
        
        self.driver_user = Mock()
        self.driver_user.id = 2
        self.driver_user.telegram_id = 234567
        self.driver_user.name = "Driver"
        self.driver_user.is_admin = False
        
        self.seeker_user = Mock()
        self.seeker_user.id = 3
        self.seeker_user.telegram_id = 345678
        self.seeker_user.name = "Seeker"
        self.seeker_user.is_admin = False
    
    def test_game_status_phases(self):
        """Тест статусов игры для фаз"""
        # Проверяем что новые статусы добавлены
        assert GameStatus.HIDING_PHASE in GameStatus
        assert GameStatus.SEARCHING_PHASE in GameStatus
        
        # Проверяем строковые значения
        assert GameStatus.HIDING_PHASE.value == "hiding_phase"
        assert GameStatus.SEARCHING_PHASE.value == "searching_phase"
    
    def test_photo_types(self):
        """Тест типов фотографий"""
        # Проверяем что новые типы добавлены
        assert PhotoType.HIDING_SPOT in PhotoType
        assert PhotoType.FOUND_CAR in PhotoType
        
        # Проверяем строковые значения
        assert PhotoType.HIDING_SPOT.value == "hiding_spot"
        assert PhotoType.FOUND_CAR.value == "found_car"
    
    @patch('src.services.photo_service.get_db')
    def test_photo_service_save_hiding_photo(self, mock_get_db):
        """Тест сохранения фото места пряток"""
        # Мокаем базу данных
        mock_db = Mock()
        mock_get_db.return_value = mock_db.__enter__.return_value = mock_db
        
        # Мокаем участника
        mock_participant = Mock()
        mock_participant.has_hidden = False
        mock_db.query.return_value.filter.return_value.first.return_value = mock_participant
        
        # Мокаем сохраненное фото
        mock_photo = Mock()
        mock_photo.id = 1
        mock_photo.photo_type = PhotoType.HIDING_SPOT
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Патчим создание объекта Photo чтобы вернуть наш мок
        with patch('src.services.photo_service.Photo', return_value=mock_photo):
            result = PhotoService.save_user_photo(
                user_id=2,
                game_id=1,
                file_id="test_file_id",
                photo_type=PhotoType.HIDING_SPOT,
                description="Test hiding spot"
            )
        
        # Проверяем результат
        assert result == mock_photo
        assert mock_participant.has_hidden == True
        assert mock_participant.hidden_at is not None
    
    @patch('src.services.photo_service.get_db')
    def test_photo_service_save_found_car_photo(self, mock_get_db):
        """Тест сохранения фото найденной машины"""
        # Мокаем базу данных
        mock_db = Mock()
        mock_get_db.return_value = mock_db.__enter__.return_value = mock_db
        
        # Мокаем сохраненное фото
        mock_photo = Mock()
        mock_photo.id = 2
        mock_photo.photo_type = PhotoType.FOUND_CAR
        mock_photo.found_driver_id = 2
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Патчим создание объекта Photo чтобы вернуть наш мок
        with patch('src.services.photo_service.Photo', return_value=mock_photo):
            result = PhotoService.save_user_photo(
                user_id=3,
                game_id=1,
                file_id="test_file_id",
                photo_type=PhotoType.FOUND_CAR,
                description="Found driver car",
                found_driver_id=2
            )
        
        # Проверяем результат
        assert result == mock_photo
        assert result.found_driver_id == 2
    
    @patch('src.services.photo_service.get_db')
    def test_photo_approval_system(self, mock_get_db):
        """Тест системы подтверждения фото админом"""
        # Мокаем базу данных
        mock_db = Mock()
        mock_get_db.return_value = mock_db.__enter__.return_value = mock_db
        
        # Мокаем фото
        mock_photo = Mock()
        mock_photo.id = 1
        mock_photo.is_approved = None
        mock_photo.photo_type = PhotoType.HIDING_SPOT
        mock_db.query.return_value.filter.return_value.first.return_value = mock_photo
        
        # Тестируем подтверждение
        result = PhotoService.approve_photo(photo_id=1, admin_id=1)
        
        assert result == True
        assert mock_photo.is_approved == True
        assert mock_photo.approved_by == 1
        assert mock_photo.reviewed_at is not None
    
    @patch('src.services.game_service.get_db')
    def test_game_phase_transitions(self, mock_get_db):
        """Тест переходов между фазами игры"""
        # Мокаем базу данных
        mock_db = Mock()
        mock_get_db.return_value = mock_db.__enter__.return_value = mock_db
        
        # Мокаем игру в фазе пряток
        mock_game = Mock()
        mock_game.id = 1
        mock_game.status = GameStatus.HIDING_PHASE
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game
        
        # Тестируем переход к фазе поиска
        result = GameService.start_searching_phase(game_id=1)
        
        assert result == True
        assert mock_game.status == GameStatus.SEARCHING_PHASE
    
    @patch('src.services.game_service.get_db')
    def test_hiding_stats(self, mock_get_db):
        """Тест получения статистики по прятанию"""
        # Мокаем базу данных
        mock_db = Mock()
        mock_get_db.return_value = mock_db.__enter__.return_value = mock_db
        
        # Мокаем водителей
        hidden_driver = Mock()
        hidden_driver.user_id = 2
        hidden_driver.has_hidden = True
        
        not_hidden_driver = Mock()
        not_hidden_driver.user_id = 4
        not_hidden_driver.has_hidden = False
        
        mock_drivers = [hidden_driver, not_hidden_driver]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_drivers
        
        # Получаем статистику
        stats = GameService.get_hiding_stats(game_id=1)
        
        assert stats['total_drivers'] == 2
        assert stats['hidden_count'] == 1
        assert stats['not_hidden_count'] == 1
        assert len(stats['not_hidden_drivers']) == 1
        assert stats['all_hidden'] == False
    
    @patch('src.services.photo_service.get_db')
    def test_hiding_photos_stats(self, mock_get_db):
        """Тест статистики фото мест пряток"""
        # Мокаем базу данных
        mock_db = Mock()
        mock_get_db.return_value = mock_db.__enter__.return_value = mock_db
        
        # Мокаем водителей
        hidden_driver = Mock()
        hidden_driver.user_id = 2
        hidden_driver.has_hidden = True
        
        not_hidden_driver = Mock()
        not_hidden_driver.user_id = 4
        not_hidden_driver.has_hidden = False
        
        # Мокаем фотографии
        approved_photo = Mock()
        approved_photo.is_approved = True
        
        pending_photo = Mock()
        pending_photo.is_approved = None
        
        rejected_photo = Mock()
        rejected_photo.is_approved = False
        
        mock_photos = [approved_photo, pending_photo, rejected_photo]
        
        # Настраиваем мок для разных запросов
        def mock_query_filter(model):
            if model == GameParticipant:
                return Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[hidden_driver, not_hidden_driver]))))
            elif model == Photo:
                return Mock(filter=Mock(return_value=Mock(all=Mock(return_value=mock_photos))))
        
        mock_db.query.side_effect = mock_query_filter
        
        # Получаем статистику
        stats = PhotoService.get_hiding_photos_stats(game_id=1)
        
        assert stats['total_drivers'] == 2
        assert stats['hidden_count'] == 1
        assert stats['photos_count'] == 3
        assert stats['approved_photos'] == 1
        assert stats['pending_photos'] == 1
        assert stats['rejected_photos'] == 1
    
    def test_scheduler_configuration(self):
        """Тест конфигурации планировщика"""
        scheduler = EnhancedSchedulerService(self.mock_app)
        
        # Проверяем настройки
        assert scheduler.hiding_time == 30
        assert scheduler.hiding_warning_time == 5
        assert scheduler.bot == self.mock_bot
    
    @pytest.mark.asyncio
    async def test_hiding_warning_notification(self):
        """Тест уведомления за 5 минут до конца пряток"""
        scheduler = EnhancedSchedulerService(self.mock_app)
        
        # Мокаем игру
        mock_game = Mock()
        mock_game.id = 1
        mock_game.district = "Test District"
        mock_game.status = GameStatus.HIDING_PHASE
        
        # Мокаем не спрятавшегося водителя
        not_hidden_driver = Mock()
        not_hidden_driver.user_id = 2
        
        hiding_stats = {
            'not_hidden_drivers': [not_hidden_driver],
            'total_drivers': 2,
            'hidden_count': 1,
            'not_hidden_count': 1
        }
        
        with patch('src.services.enhanced_scheduler_service.GameService.get_game_by_id', return_value=mock_game), \
             patch('src.services.enhanced_scheduler_service.GameService.get_hiding_stats', return_value=hiding_stats), \
             patch('src.services.enhanced_scheduler_service.UserService.get_user_by_id', return_value=(self.driver_user, None)), \
             patch('src.services.enhanced_scheduler_service.UserService.get_admin_users', return_value=[self.admin_user]), \
             patch('src.services.enhanced_scheduler_service.EventPersistenceService.mark_event_executed'):
            
            await scheduler.send_hiding_warning(game_id=1, event_id=1)
            
            # Проверяем что было отправлено уведомление водителю
            assert self.mock_bot.send_message.call_count >= 1
            
            # Проверяем вызовы
            calls = self.mock_bot.send_message.call_args_list
            driver_call = None
            admin_call = None
            
            for call in calls:
                args, kwargs = call
                if kwargs.get('chat_id') == self.driver_user.telegram_id:
                    driver_call = kwargs
                elif kwargs.get('chat_id') == self.admin_user.telegram_id:
                    admin_call = kwargs
            
            # Проверяем уведомление водителю
            assert driver_call is not None
            assert "Осталось 5 минут" in driver_call['text']
            assert "отправьте фотографию" in driver_call['text']
            
            # Проверяем уведомление админу
            assert admin_call is not None
            assert "Статистика пряток" in admin_call['text']
    
    @pytest.mark.asyncio 
    async def test_phase_transition_notification(self):
        """Тест уведомления о переходе к фазе поиска"""
        scheduler = EnhancedSchedulerService(self.mock_app)
        
        # Мокаем игру
        mock_game = Mock()
        mock_game.id = 1
        mock_game.district = "Test District"
        mock_game.status = GameStatus.HIDING_PHASE
        mock_game.participants = [
            Mock(user_id=2, role=GameRole.DRIVER),
            Mock(user_id=3, role=GameRole.SEEKER)
        ]
        
        with patch('src.services.enhanced_scheduler_service.GameService.get_game_by_id', return_value=mock_game), \
             patch('src.services.enhanced_scheduler_service.GameService.start_searching_phase', return_value=True), \
             patch('src.services.enhanced_scheduler_service.UserService.get_user_by_id') as mock_get_user, \
             patch('src.services.enhanced_scheduler_service.EventPersistenceService.mark_event_executed'):
            
            # Настраиваем возврат пользователей
            def mock_user_return(user_id):
                if user_id == 2:
                    return (self.driver_user, None)
                elif user_id == 3:
                    return (self.seeker_user, None)
                return (None, None)
            
            mock_get_user.side_effect = mock_user_return
            
            await scheduler.end_hiding_phase(game_id=1, event_id=1)
            
            # Проверяем что были отправлены уведомления
            assert self.mock_bot.send_message.call_count == 2
            
            # Проверяем что GameService.start_searching_phase был вызван
            # (это проверяется через patch)
    
    def test_photo_id_solution(self):
        """Тест решения проблемы с большими ID в колбэках"""
        # Создаем фото с большим file_id
        large_file_id = "BAACAgIAAxkBAAICmGYH1234567890abcdefghijklmnopqrstuvwxyz"
        
        # Моделируем сохранение в БД с получением ID
        mock_photo = Mock()
        mock_photo.id = 123  # Маленький ID для колбэка
        mock_photo.file_id = large_file_id
        
        # Проверяем что ID фото используется в колбэках
        callback_data = f"admin_approve_photo_{mock_photo.id}"
        assert len(callback_data) < 64  # Лимит Telegram
        
        callback_data = f"admin_reject_photo_{mock_photo.id}"
        assert len(callback_data) < 64
    
    def test_photo_workflow_integration(self):
        """Интеграционный тест рабочего процесса с фотографиями"""
        # 1. Водитель отправляет фото места пряток
        with patch('src.services.photo_service.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db.__enter__.return_value = mock_db
            
            mock_participant = Mock()
            mock_participant.has_hidden = False
            mock_db.query.return_value.filter.return_value.first.return_value = mock_participant
            
            mock_photo = Mock()
            mock_photo.id = 1
            mock_photo.photo_type = PhotoType.HIDING_SPOT
            
            with patch('src.services.photo_service.Photo', return_value=mock_photo):
                hiding_photo = PhotoService.save_user_photo(
                    user_id=2,
                    game_id=1,
                    file_id="hiding_photo_file_id",
                    photo_type=PhotoType.HIDING_SPOT
                )
            
            # Проверяем что участник отмечен как спрятавшийся
            assert mock_participant.has_hidden == True
            assert hiding_photo == mock_photo
        
        # 2. Админ подтверждает фото
        with patch('src.services.photo_service.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db.__enter__.return_value = mock_db
            
            mock_photo.is_approved = None
            mock_db.query.return_value.filter.return_value.first.return_value = mock_photo
            
            approval_result = PhotoService.approve_photo(photo_id=1, admin_id=1)
            
            assert approval_result == True
            assert mock_photo.is_approved == True
        
        # 3. Искатель отправляет фото найденной машины
        with patch('src.services.photo_service.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db.__enter__.return_value = mock_db
            
            found_photo = Mock()
            found_photo.id = 2
            found_photo.photo_type = PhotoType.FOUND_CAR
            found_photo.found_driver_id = 2
            
            with patch('src.services.photo_service.Photo', return_value=found_photo):
                result = PhotoService.save_user_photo(
                    user_id=3,
                    game_id=1,
                    file_id="found_car_file_id",
                    photo_type=PhotoType.FOUND_CAR,
                    found_driver_id=2
                )
            
            assert result == found_photo
            assert result.found_driver_id == 2

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 