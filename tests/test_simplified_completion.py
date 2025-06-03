import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, User, CallbackQuery
from telegram.ext import ContextTypes

from src.services.user_service import UserService
from src.services.game_service import GameService
from src.models.game import Game, GameStatus, GameRole, GameParticipant
from src.models.user import User as UserModel, UserRole
from src.handlers.callback_handler import (
    notify_drivers_about_found,
    notify_participants_about_found_driver, 
    check_game_completion_callback,
    notify_game_completion_callback
)


class TestSimplifiedGameCompletion:
    """Упрощённые тесты завершения игры с фокусом на логику уведомлений"""
    
    @pytest.fixture
    def mock_context(self):
        """Создание мок-объекта Context"""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        return context
    
    @pytest.fixture
    def simple_game_with_participants(self):
        """Создание простой игры с участниками"""
        game = Mock()
        game.id = 1
        game.district = "Тестовый"
        game.status = GameStatus.HIDING_PHASE
        game.started_at = datetime.now() - timedelta(minutes=30)
        game.ended_at = None
        
        # Создаем участников
        participants = []
        
        # 2 водителя
        for i in range(2):
            participant = Mock()
            participant.user_id = i + 1
            participant.role = Mock()
            participant.role.value = 'driver'
            participant.is_found = False
            participant.user = Mock()
            participant.user.name = f"Водитель {i + 1}"
            participant.user.telegram_id = 1000 + i
            participants.append(participant)
        
        # 3 искателя
        for i in range(3):
            participant = Mock()
            participant.user_id = i + 3
            participant.role = Mock()
            participant.role.value = 'seeker'
            participant.is_found = False
            participant.user = Mock()
            participant.user.name = f"Искатель {i + 1}"
            participant.user.telegram_id = 2000 + i
            participants.append(participant)
        
        game.participants = participants
        return game

    @pytest.mark.asyncio
    async def test_notify_drivers_about_found_simple(self, mock_context, simple_game_with_participants):
        """Простой тест уведомления водителей"""
        print("\n=== ТЕСТ: Простое уведомление водителей ===")
        
        game = simple_game_with_participants
        seeker_name = "Тест Искатель"
        
        with patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                for participant in game.participants:
                    if participant.user_id == user_id:
                        return participant.user, True
                return None, False
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем уведомление водителям
            await notify_drivers_about_found(mock_context, game.id, seeker_name)
            
            # Проверяем количество отправленных сообщений (только водителям)
            drivers_count = len([p for p in game.participants if p.role.value == 'driver'])
            assert mock_context.bot.send_message.call_count == drivers_count
            
        print(f"✅ Отправлено {drivers_count} уведомлений водителям")

    @pytest.mark.asyncio
    async def test_notify_participants_about_found_driver_simple(self, mock_context, simple_game_with_participants):
        """Простой тест уведомления участников о найденном водителе"""
        print("\n=== ТЕСТ: Простое уведомление о найденном водителе ===")
        
        game = simple_game_with_participants
        driver_name = game.participants[0].user.name  # Имя первого водителя
        
        with patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                for participant in game.participants:
                    if participant.user_id == user_id:
                        return participant.user, True
                return None, False
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем уведомление участникам
            await notify_participants_about_found_driver(mock_context, game.id, driver_name)
            
            # Проверяем количество отправленных сообщений (всем кроме найденного водителя)
            expected_messages = len([p for p in game.participants if p.user.name != driver_name])
            assert mock_context.bot.send_message.call_count == expected_messages
            
        print(f"✅ Отправлено {expected_messages} уведомлений участникам")

    @pytest.mark.asyncio
    async def test_check_game_completion_not_finished_simple(self, mock_context, simple_game_with_participants):
        """Простой тест проверки завершения - игра не завершена"""
        print("\n=== ТЕСТ: Игра не завершена ===")
        
        game = simple_game_with_participants
        
        # Только один водитель найден
        game.participants[0].is_found = True
        game.participants[1].is_found = False
        
        with patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch('src.handlers.callback_handler.notify_game_completion_callback') as mock_completion:
            
            # Проверяем завершение игры
            await check_game_completion_callback(mock_context, game.id)
            
            # Проверяем, что игра НЕ завершена
            mock_completion.assert_not_called()
            
        print("✅ Игра корректно продолжается")

    @pytest.mark.asyncio
    async def test_check_game_completion_finished_simple(self, mock_context, simple_game_with_participants):
        """Простой тест проверки завершения - игра завершена"""
        print("\n=== ТЕСТ: Игра завершена ===")
        
        game = simple_game_with_participants
        
        # Все водители найдены
        for participant in game.participants:
            if participant.role.value == 'driver':
                participant.is_found = True
                participant.found_at = datetime.now()
        
        with patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch.object(GameService, 'end_game', return_value=True), \
             patch('src.handlers.callback_handler.notify_game_completion_callback') as mock_completion:
            
            # Проверяем завершение игры
            await check_game_completion_callback(mock_context, game.id)
            
            # Проверяем завершение игры
            GameService.end_game.assert_called_once_with(game.id)
            mock_completion.assert_called_once_with(mock_context, game.id)
            
        print("✅ Игра корректно завершается")

    @pytest.mark.asyncio
    async def test_notify_game_completion_simple(self, mock_context, simple_game_with_participants):
        """Простой тест уведомления о завершении игры"""
        print("\n=== ТЕСТ: Уведомление о завершении ===")
        
        game = simple_game_with_participants
        game.status = GameStatus.COMPLETED
        game.ended_at = datetime.now()
        
        # Отмечаем всех водителей как найденных
        for participant in game.participants:
            if participant.role.value == 'driver':
                participant.is_found = True
                participant.found_at = datetime.now() - timedelta(minutes=10)
        
        with patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                for participant in game.participants:
                    if participant.user_id == user_id:
                        return participant.user, True
                return None, False
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем уведомление о завершении
            await notify_game_completion_callback(mock_context, game.id)
            
            # Проверяем количество отправленных сообщений
            assert mock_context.bot.send_message.call_count == len(game.participants)
            
        print(f"✅ Отправлено {len(game.participants)} уведомлений о завершении")

    @pytest.mark.asyncio
    async def test_full_notification_sequence(self, mock_context, simple_game_with_participants):
        """Тест полной последовательности уведомлений"""
        print("\n=== ТЕСТ: Полная последовательность уведомлений ===")
        
        game = simple_game_with_participants
        
        with patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user, \
             patch.object(GameService, 'end_game', return_value=True):
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                for participant in game.participants:
                    if participant.user_id == user_id:
                        return participant.user, True
                return None, False
            mock_get_user.side_effect = get_user_side_effect
            
            print("1. Уведомления водителям о находке...")
            await notify_drivers_about_found(mock_context, game.id, "Искатель 1")
            drivers_notified = mock_context.bot.send_message.call_count
            
            print("2. Уведомления о найденном водителе...")
            await notify_participants_about_found_driver(mock_context, game.id, "Водитель 1")
            participants_notified = mock_context.bot.send_message.call_count - drivers_notified
            
            print("3. Завершение игры...")
            # Отмечаем всех водителей как найденных
            for participant in game.participants:
                if participant.role.value == 'driver':
                    participant.is_found = True
            
            await check_game_completion_callback(mock_context, game.id)
            
            print("4. Уведомления о завершении...")
            await notify_game_completion_callback(mock_context, game.id)
            completion_notified = mock_context.bot.send_message.call_count - drivers_notified - participants_notified
            
            # Проверяем общее количество уведомлений
            total_notifications = mock_context.bot.send_message.call_count
            assert total_notifications > 0
            
            print(f"✅ Всего отправлено {total_notifications} уведомлений:")
            print(f"   • Водителям о находке: {drivers_notified}")
            print(f"   • Участникам о найденном водителе: {participants_notified}")
            print(f"   • О завершении игры: {completion_notified}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"]) 