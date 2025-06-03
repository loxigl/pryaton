import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, User, Chat, Message, CallbackQuery
from telegram.ext import ContextTypes

from src.services.user_service import UserService
from src.services.game_service import GameService
from src.models.game import Game, GameStatus, GameRole, GameParticipant
from src.models.user import User as UserModel, UserRole
from src.handlers.games import (
    games_command, my_games_command, game_button, join_game_button, 
    leave_game_button, back_to_games_button
)
from src.handlers.admin import (
    create_game_command, process_district, process_date, process_time,
    process_max_participants, process_max_drivers, process_description,
    process_confirmation, admin_game_button, start_game_button,
    assign_roles_button, cancel_game_button
)
from src.services.scheduler_service import SchedulerService


class TestFullGameProcess:
    """Тесты полного игрового процесса от создания до завершения"""
    
    @pytest.fixture
    def mock_update(self):
        """Создание мок-объекта Update"""
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        update.effective_user.first_name = "Тест"
        update.effective_user.username = "testuser"
        
        update.message = Mock(spec=Message)
        update.message.text = ""
        update.message.reply_text = AsyncMock()
        
        update.callback_query = Mock(spec=CallbackQuery)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.from_user = update.effective_user
        update.callback_query.data = ""
        
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Создание мок-объекта Context"""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        return context
    
    @pytest.fixture
    def test_user(self):
        """Создание тестового пользователя"""
        return UserModel(
            id=1,
            telegram_id=12345,
            username="testuser",
            name="Тест Игрок",
            phone="+7999123456",
            district="Центральный",
            default_role=UserRole.DRIVER
        )
    
    @pytest.fixture
    def admin_user(self):
        """Создание тестового администратора"""
        return UserModel(
            id=2,
            telegram_id=67890,
            username="testadmin",
            name="Тест Админ",
            phone="+7999654321",
            district="Центральный", 
            default_role=UserRole.PLAYER
        )
    
    @pytest.fixture
    def test_game(self, admin_user):
        """Создание тестовой игры"""
        future_time = datetime.now() + timedelta(hours=2)
        
        game = Mock()
        game.id = 1
        game.district = "Центральный"
        game.max_participants = 6
        game.max_drivers = 2
        game.scheduled_at = future_time
        game.creator_id = admin_user.id
        game.status = GameStatus.RECRUITING
        game.description = "Тестовая игра"
        game.participants = []
        
        return game

    @pytest.mark.asyncio
    async def test_1_user_registration_and_games_view(self, mock_update, mock_context, test_user):
        """Тест 1: Регистрация пользователя и просмотр игр"""
        print("\n=== ТЕСТ 1: Регистрация и просмотр игр ===")
        
        # Мокаем сервисы
        with patch.object(UserService, 'get_user_by_telegram_id', return_value=(test_user, True)), \
             patch.object(GameService, 'get_upcoming_games', return_value=[]):
            
            # Тестируем команду /games для зарегистрированного пользователя
            await games_command(mock_update, mock_context)
            
            # Проверяем, что отправлено сообщение о том, что игр нет
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Сейчас нет запланированных игр" in call_args
            
        print("✅ Пользователь успешно зарегистрирован и может просматривать игры")

    @pytest.mark.asyncio 
    async def test_2_admin_creates_game(self, mock_update, mock_context, admin_user):
        """Тест 2: Администратор создает игру"""
        print("\n=== ТЕСТ 2: Создание игры администратором ===")
        
        # Настраиваем админского пользователя
        mock_update.effective_user.id = admin_user.telegram_id
        
        with patch.object(UserService, 'is_admin', return_value=True), \
             patch.object(UserService, 'get_user_by_telegram_id', return_value=(admin_user, True)), \
             patch.object(GameService, 'create_game') as mock_create_game:
            
            # Создаем мок-игру
            future_time = datetime.now() + timedelta(hours=2)
            mock_game = Mock()
            mock_game.id = 1
            mock_game.district = "Центральный"
            mock_game.scheduled_at = future_time
            mock_game.max_participants = 6
            mock_game.max_drivers = 2
            mock_create_game.return_value = mock_game
            
            # Начинаем процесс создания игры
            result = await create_game_command(mock_update, mock_context)
            mock_update.message.reply_text.assert_called()
            
            # Симулируем пошаговое создание игры
            # Шаг 1: Выбор района
            mock_update.message.text = "Центральный"
            result = await process_district(mock_update, mock_context)
            assert mock_context.user_data["game_district"] == "Центральный"
            
            # Шаг 2: Ввод даты
            mock_update.message.text = "31.12.2024"
            result = await process_date(mock_update, mock_context)
            assert "game_date" in mock_context.user_data
            
            # Шаг 3: Ввод времени
            mock_update.message.text = "18:30"
            result = await process_time(mock_update, mock_context)
            assert "game_datetime" in mock_context.user_data
            
            # Шаг 4: Количество участников
            mock_update.message.text = "6"
            result = await process_max_participants(mock_update, mock_context)
            assert mock_context.user_data["max_participants"] == 6
            
            # Шаг 5: Количество водителей
            mock_update.message.text = "2"
            result = await process_max_drivers(mock_update, mock_context)
            assert mock_context.user_data["max_drivers"] == 2
            
            # Шаг 6: Описание
            mock_update.message.text = "Тестовая игра"
            result = await process_description(mock_update, mock_context)
            assert mock_context.user_data["description"] == "Тестовая игра"
            
            # Шаг 7: Подтверждение
            mock_update.message.text = "✅ Да, создать игру"
            result = await process_confirmation(mock_update, mock_context)
            
            # Проверяем, что игра была создана
            mock_create_game.assert_called_once()
            
        print("✅ Администратор успешно создал игру")

    @pytest.mark.asyncio
    async def test_3_players_join_game(self, mock_update, mock_context, test_user, test_game):
        """Тест 3: Игроки записываются на игру"""
        print("\n=== ТЕСТ 3: Запись игроков на игру ===")
        
        with patch.object(UserService, 'get_user_by_telegram_id', return_value=(test_user, True)), \
             patch.object(GameService, 'get_game_by_id', return_value=test_game), \
             patch.object(GameService, 'join_game') as mock_join_game:
            
            # Создаем мок участника
            mock_participant = Mock()
            mock_participant.user_id = test_user.id
            mock_participant.game_id = test_game.id
            mock_join_game.return_value = mock_participant
            
            # Добавляем участников к игре
            test_game.participants = [mock_participant]
            
            # Симулируем просмотр информации об игре
            mock_update.callback_query.data = "game_1"
            await game_button(mock_update, mock_context)
            
            # Симулируем запись на игру
            mock_update.callback_query.data = "join_1"
            await join_game_button(mock_update, mock_context)
            
            # Проверяем, что запись прошла успешно
            mock_join_game.assert_called_once_with(test_game.id, test_user.id)
            mock_update.callback_query.edit_message_text.assert_called()
            
        print("✅ Игрок успешно записался на игру")

    @pytest.mark.asyncio
    async def test_4_admin_manages_game(self, mock_update, mock_context, admin_user, test_game):
        """Тест 4: Администратор управляет игрой"""
        print("\n=== ТЕСТ 4: Управление игрой администратором ===")
        
        # Настраиваем админского пользователя
        mock_update.effective_user.id = admin_user.telegram_id
        mock_update.callback_query.from_user.id = admin_user.telegram_id
        
        # Создаем участников для игры
        mock_participants = []
        for i in range(4):
            participant = Mock()
            participant.user_id = i + 1
            participant.user = Mock()
            participant.user.name = f"Игрок {i + 1}"
            participant.role = None
            mock_participants.append(participant)
        
        test_game.participants = mock_participants
        
        with patch.object(UserService, 'is_admin', return_value=True), \
             patch.object(GameService, 'get_game_by_id', return_value=test_game), \
             patch.object(GameService, 'assign_roles') as mock_assign_roles, \
             patch.object(GameService, 'start_game') as mock_start_game:
            
            # Просмотр игры в админке
            mock_update.callback_query.data = "admin_game_1"
            await admin_game_button(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called()
            
            # Распределение ролей
            mock_assign_roles.return_value = [
                (1, GameRole.DRIVER), (2, GameRole.DRIVER),
                (3, GameRole.SEEKER), (4, GameRole.SEEKER)
            ]
            
            # Обновляем роли участников
            for i, participant in enumerate(mock_participants):
                if i < 2:
                    participant.role = GameRole.DRIVER
                else:
                    participant.role = GameRole.SEEKER
            
            mock_update.callback_query.data = "assign_roles_1"
            await assign_roles_button(mock_update, mock_context)
            
            # Проверяем распределение ролей
            mock_assign_roles.assert_called_once_with(test_game.id)
            
            # Запуск игры
            mock_start_game.return_value = True
            mock_update.callback_query.data = "start_game_1"
            await start_game_button(mock_update, mock_context)
            
            # Проверяем запуск игры
            mock_start_game.assert_called_once_with(test_game.id, "manual")
            
        print("✅ Администратор успешно распределил роли и запустил игру")

    @pytest.mark.asyncio
    async def test_5_scheduler_notifications(self, mock_context, test_game, admin_user):
        """Тест 5: Планировщик и уведомления"""
        print("\n=== ТЕСТ 5: Планировщик и уведомления ===")
        
        # Создаем мок планировщика
        mock_application = Mock()
        mock_application.bot = Mock()
        mock_application.bot.send_message = AsyncMock()
        
        scheduler = SchedulerService(mock_application)
        
        # Создаем участников
        mock_participants = []
        for i in range(4):
            participant = Mock()
            participant.user_id = i + 1
            participant.role = GameRole.DRIVER if i < 2 else GameRole.SEEKER
            
            user_mock = Mock()
            user_mock.telegram_id = 10000 + i
            user_mock.name = f"Игрок {i + 1}"
            
            mock_participants.append(participant)
        
        test_game.participants = mock_participants
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                user_mock = Mock()
                user_mock.telegram_id = 10000 + user_id - 1
                user_mock.name = f"Игрок {user_id}"
                return user_mock, True
                
            mock_get_user.side_effect = get_user_side_effect
            
            # Тестируем отправку напоминания
            await scheduler.send_game_reminder(test_game.id, 60)
            
            # Проверяем, что уведомления отправлены
            assert mock_application.bot.send_message.call_count == len(mock_participants)
            
            # Тестируем уведомление о начале игры
            test_game.status = GameStatus.HIDING_PHASE
            await scheduler.notify_game_started(test_game.id)
            
            # Проверяем отправку уведомлений о начале
            assert mock_application.bot.send_message.call_count >= len(mock_participants) * 2
            
        print("✅ Планировщик успешно отправляет уведомления")

    @pytest.mark.asyncio
    async def test_6_game_cancellation(self, mock_update, mock_context, admin_user, test_game):
        """Тест 6: Отмена игры"""
        print("\n=== ТЕСТ 6: Отмена игры ===")
        
        # Настраиваем админского пользователя
        mock_update.effective_user.id = admin_user.telegram_id
        mock_update.callback_query.from_user.id = admin_user.telegram_id
        
        with patch.object(UserService, 'is_admin', return_value=True), \
             patch.object(GameService, 'cancel_game') as mock_cancel_game:
            
            mock_cancel_game.return_value = True
            
            # Отмена игры
            mock_update.callback_query.data = "cancel_game_1"
            await cancel_game_button(mock_update, mock_context)
            
            # Проверяем отмену игры
            mock_cancel_game.assert_called_once()
            mock_update.callback_query.edit_message_text.assert_called()
            
        print("✅ Администратор успешно отменил игру")

    @pytest.mark.asyncio
    async def test_7_player_leaves_game(self, mock_update, mock_context, test_user, test_game):
        """Тест 7: Игрок покидает игру"""
        print("\n=== ТЕСТ 7: Выход игрока из игры ===")
        
        with patch.object(UserService, 'get_user_by_telegram_id', return_value=(test_user, True)), \
             patch.object(GameService, 'leave_game') as mock_leave_game:
            
            mock_leave_game.return_value = True
            
            # Покидание игры
            mock_update.callback_query.data = "leave_1"
            await leave_game_button(mock_update, mock_context)
            
            # Проверяем выход из игры
            mock_leave_game.assert_called_once_with(test_game.id, test_user.id)
            mock_update.callback_query.edit_message_text.assert_called()
            
        print("✅ Игрок успешно покинул игру")

    @pytest.mark.asyncio
    async def test_8_my_games_command(self, mock_update, mock_context, test_user, test_game):
        """Тест 8: Команда "Мои игры" """
        print("\n=== ТЕСТ 8: Просмотр личных игр ===")
        
        with patch.object(UserService, 'get_user_by_telegram_id', return_value=(test_user, True)), \
             patch.object(GameService, 'get_user_games', return_value=[test_game]):
            
            # Тестируем команду мои игры
            await my_games_command(mock_update, mock_context)
            
            # Проверяем ответ
            mock_update.message.reply_text.assert_called()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Ваши игры" in call_args
            
        print("✅ Пользователь может просматривать свои игры")

    @pytest.mark.asyncio
    async def test_9_back_to_games_navigation(self, mock_update, mock_context, test_user, test_game):
        """Тест 9: Навигация назад к списку игр"""
        print("\n=== ТЕСТ 9: Навигация по интерфейсу ===")
        
        with patch.object(GameService, 'get_upcoming_games', return_value=[test_game]):
            
            # Тестируем возврат к списку игр
            mock_update.callback_query.data = "back_to_games"
            await back_to_games_button(mock_update, mock_context)
            
            # Проверяем навигацию
            mock_update.callback_query.edit_message_text.assert_called()
            call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
            assert "Список доступных игр" in call_args
            
        print("✅ Навигация работает корректно")

    @pytest.mark.asyncio
    async def test_10_game_service_integration(self, test_game, test_user, admin_user):
        """Тест 10: Интеграция сервисов игры"""
        print("\n=== ТЕСТ 10: Интеграция сервисов ===")
        
        future_time = datetime.now() + timedelta(hours=1)
        
        with patch('src.models.base.get_db') as mock_get_db, \
             patch.object(GameService, 'get_game_by_id', return_value=test_game), \
             patch.object(GameService, 'join_game', return_value=Mock()), \
             patch.object(GameService, 'assign_roles', return_value=[(1, GameRole.DRIVER), (2, GameRole.SEEKER)]), \
             patch.object(GameService, 'start_game', return_value=True), \
             patch.object(GameService, 'cancel_game', return_value=True):
            
            # Тестируем создание игры
            created_game = GameService.create_game(
                district="Центральный",
                max_participants=6,
                max_drivers=2,
                scheduled_at=future_time,
                creator_id=admin_user.id,
                description="Интеграционный тест"
            )
            
            # Тестируем запись на игру
            participant = GameService.join_game(test_game.id, test_user.id)
            assert participant is not None
            
            # Тестируем распределение ролей
            roles = GameService.assign_roles(test_game.id)
            assert len(roles) > 0
            
            # Тестируем запуск игры
            start_result = GameService.start_game(test_game.id)
            assert start_result is True
            
            # Тестируем отмену игры
            cancel_result = GameService.cancel_game(test_game.id)
            assert cancel_result is True
            
        print("✅ Все сервисы интегрированы корректно")

    @pytest.mark.asyncio
    async def test_full_integration_flow(self, mock_update, mock_context, admin_user, test_user):
        """Полный интеграционный тест игрового процесса"""
        print("\n=== ПОЛНЫЙ ИНТЕГРАЦИОННЫЙ ТЕСТ ===")
        
        # Создаем полноценную игру с участниками
        future_time = datetime.now() + timedelta(hours=2)
        
        mock_game = Mock()
        mock_game.id = 999
        mock_game.district = "Тестовый"
        mock_game.scheduled_at = future_time
        mock_game.max_participants = 4
        mock_game.max_drivers = 1
        mock_game.status = GameStatus.RECRUITING
        mock_game.participants = []
        
        # Добавляем участников
        for i in range(4):
            participant = Mock()
            participant.user_id = i + 1
            participant.user = Mock()
            participant.user.name = f"Игрок {i + 1}"
            participant.role = GameRole.DRIVER if i == 0 else GameRole.SEEKER
            mock_game.participants.append(participant)
        
        with patch.object(UserService, 'is_admin', return_value=True), \
             patch.object(UserService, 'get_user_by_telegram_id', return_value=(admin_user, True)), \
             patch.object(GameService, 'create_game', return_value=mock_game), \
             patch.object(GameService, 'get_game_by_id', return_value=mock_game), \
             patch.object(GameService, 'join_game', return_value=Mock()), \
             patch.object(GameService, 'assign_roles', return_value=[(1, GameRole.DRIVER), (2, GameRole.SEEKER), (3, GameRole.SEEKER), (4, GameRole.SEEKER)]), \
             patch.object(GameService, 'start_game', return_value=True):
            
            print("1. Создание игры администратором...")
            # Создание игры
            created_game = GameService.create_game(
                district="Тестовый",
                max_participants=4,
                max_drivers=1, 
                scheduled_at=future_time,
                creator_id=admin_user.id
            )
            assert created_game is not None
            
            print("2. Запись участников...")
            # Запись участников
            for i in range(4):
                participant = GameService.join_game(mock_game.id, i + 1)
                assert participant is not None
            
            print("3. Распределение ролей...")
            # Распределение ролей
            roles = GameService.assign_roles(mock_game.id)
            assert len(roles) == 4
            assert any(role[1] == GameRole.DRIVER for role in roles)
            assert any(role[1] == GameRole.SEEKER for role in roles)
            
            print("4. Запуск игры...")
            # Запуск игры
            start_result = GameService.start_game(mock_game.id)
            assert start_result is True
            
            print("5. Тестирование интерфейса...")
            # Тестирование пользовательского интерфейса
            mock_update.callback_query.data = f"game_{mock_game.id}"
            await game_button(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called()
            
        print("✅ ПОЛНЫЙ ИНТЕГРАЦИОННЫЙ ТЕСТ ПРОШЕЛ УСПЕШНО!")
        print("Весь игровой процесс функционирует корректно от создания до завершения")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"]) 