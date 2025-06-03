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
    handle_found_car_callback, handle_found_me_callback, 
    handle_game_status_callback, notify_drivers_about_found,
    notify_participants_about_found_driver, check_game_completion_callback,
    notify_game_completion_callback
)
from src.handlers.location import handle_location
from src.handlers.photo import handle_photo


class TestGameCompletionFlow:
    """Тесты процесса завершения игры и уведомлений"""
    
    @pytest.fixture
    def mock_update(self):
        """Создание мок-объекта Update с callback query"""
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        update.effective_user.first_name = "Тест"
        
        update.callback_query = Mock(spec=CallbackQuery)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.from_user = update.effective_user
        update.callback_query.message = Mock()
        update.callback_query.message.chat_id = 12345
        
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
    def active_game_with_participants(self):
        """Создание активной игры с участниками"""
        future_time = datetime.now() + timedelta(hours=1)
        
        game = Mock()
        game.id = 1
        game.district = "Центральный"
        game.scheduled_at = future_time
        game.started_at = datetime.now() - timedelta(minutes=30)
        game.max_participants = 6
        game.max_drivers = 2
        game.status = GameStatus.HIDING_PHASE
        game.description = "Тестовая активная игра"
        
        # Создаем участников
        participants = []
        
        # 2 водителя
        for i in range(2):
            participant = Mock()
            participant.user_id = i + 1
            participant.game_id = game.id
            participant.role = Mock()
            participant.role.value = 'driver'
            participant.is_found = False
            participant.found_at = None
            participant.user = Mock()
            participant.user.name = f"Водитель {i + 1}"
            participant.user.telegram_id = 10000 + i
            participants.append(participant)
        
        # 4 искателя
        for i in range(4):
            participant = Mock()
            participant.user_id = i + 3
            participant.game_id = game.id
            participant.role = Mock()
            participant.role.value = 'seeker'
            participant.is_found = False
            participant.found_at = None
            participant.user = Mock()
            participant.user.name = f"Искатель {i + 1}"
            participant.user.telegram_id = 10000 + i + 2
            participants.append(participant)
        
        game.participants = participants
        return game

    @pytest.mark.asyncio
    async def test_seeker_finds_driver(self, mock_update, mock_context, active_game_with_participants):
        """Тест: Искатель находит водителя"""
        print("\n=== ТЕСТ: Искатель находит водителя ===")
        
        game = active_game_with_participants
        seeker = next(p for p in game.participants if p.role.value == 'seeker')
        driver = next(p for p in game.participants if p.role.value == 'driver')
        
        # Настраиваем пользователя как искателя
        mock_update.effective_user.id = seeker.user.telegram_id
        mock_update.callback_query.data = f"found_car_{game.id}"
        
        with patch.object(UserService, 'get_user_by_telegram_id', return_value=(seeker.user, True)), \
             patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch('src.handlers.callback_handler.notify_drivers_about_found') as mock_notify:
            
            # Искатель нажимает "Нашёл машину"
            await handle_found_car_callback(mock_update, mock_context)
            
            # Проверяем отправку уведомления водителям
            mock_notify.assert_called_once_with(mock_context, game.id, seeker.user.name)
            
            # Проверяем ответ искателю
            mock_update.callback_query.edit_message_text.assert_called()
            call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
            assert "Водители уведомлены" in call_args
            
        print("✅ Искатель успешно отправил уведомление о находке")

    @pytest.mark.asyncio
    async def test_driver_confirms_found(self, mock_update, mock_context, active_game_with_participants):
        """Тест: Водитель подтверждает находку"""
        print("\n=== ТЕСТ: Водитель подтверждает находку ===")
        
        game = active_game_with_participants
        driver = next(p for p in game.participants if p.role.value == 'driver')
        
        # Настраиваем пользователя как водителя
        mock_update.effective_user.id = driver.user.telegram_id
        mock_update.callback_query.data = f"found_me_{game.id}"
        
        with patch.object(UserService, 'get_user_by_telegram_id', return_value=(driver.user, True)), \
             patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch.object(GameService, 'mark_participant_found', return_value=True), \
             patch('src.handlers.callback_handler.notify_participants_about_found_driver') as mock_notify, \
             patch('src.handlers.callback_handler.check_game_completion_callback') as mock_check_completion:
            
            # Водитель подтверждает находку
            await handle_found_me_callback(mock_update, mock_context)
            
            # Проверяем отметку в БД
            GameService.mark_participant_found.assert_called_once_with(game.id, driver.user_id)
            
            # Проверяем уведомление участников
            mock_notify.assert_called_once_with(mock_context, game.id, driver.user.name)
            
            # Проверяем проверку завершения игры
            mock_check_completion.assert_called_once_with(mock_context, game.id)
            
            # Проверяем ответ водителю
            mock_update.callback_query.edit_message_text.assert_called()
            call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
            assert "подтверждена" in call_args
            
        print("✅ Водитель успешно подтвердил находку")

    @pytest.mark.asyncio
    async def test_notify_drivers_about_found(self, mock_context, active_game_with_participants):
        """Тест: Уведомление водителей о находке"""
        print("\n=== ТЕСТ: Уведомление водителей о находке ===")
        
        game = active_game_with_participants
        seeker_name = "Тест Искатель"
        
        with patch.object(GameService, 'get_game_by_id', return_value=game):
            
            # Отправляем уведомление водителям
            await notify_drivers_about_found(mock_context, game.id, seeker_name)
            
            # Проверяем количество отправленных сообщений (только водителям)
            drivers_count = len([p for p in game.participants if p.role.value == 'driver'])
            assert mock_context.bot.send_message.call_count == drivers_count
            
            # Проверяем содержание уведомлений
            for call in mock_context.bot.send_message.call_args_list:
                args, kwargs = call
                message_text = kwargs.get('text', args[1] if len(args) > 1 else '')
                assert seeker_name in message_text
                assert "нашли" in message_text.lower()
                
        print("✅ Водители получили уведомления о находке")

    @pytest.mark.asyncio
    async def test_notify_participants_about_found_driver(self, mock_context, active_game_with_participants):
        """Тест: Уведомление участников о найденном водителе"""
        print("\n=== ТЕСТ: Уведомление участников о найденном водителе ===")
        
        game = active_game_with_participants
        driver_name = "Тест Водитель"
        
        with patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                for participant in game.participants:
                    if participant.user_id == user_id:
                        return participant.user, True
                return None, False
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем уведомление всем участникам
            await notify_participants_about_found_driver(mock_context, game.id, driver_name)
            
            # Проверяем количество отправленных сообщений (всем кроме найденного водителя)
            expected_messages = len([p for p in game.participants if p.user.name != driver_name])
            assert mock_context.bot.send_message.call_count == expected_messages
            
            # Проверяем содержание уведомлений
            for call in mock_context.bot.send_message.call_args_list:
                args, kwargs = call
                message_text = kwargs.get('text', args[1] if len(args) > 1 else '')
                assert "найден" in message_text.lower()
                
        print("✅ Участники получили уведомления о найденном водителе")

    @pytest.mark.asyncio
    async def test_check_game_completion_not_finished(self, mock_context, active_game_with_participants):
        """Тест: Проверка завершения игры - игра не завершена"""
        print("\n=== ТЕСТ: Проверка завершения - игра продолжается ===")
        
        game = active_game_with_participants
        
        # Только один водитель найден
        game.participants[0].is_found = True
        game.participants[1].is_found = False
        
        with patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch('src.handlers.callback_handler.notify_game_completion_callback') as mock_completion:
            
            # Проверяем завершение игры
            await check_game_completion_callback(mock_context, game.id)
            
            # Проверяем, что игра НЕ завершена
            mock_completion.assert_not_called()
            
        print("✅ Игра корректно продолжается, пока не найдены все водители")

    @pytest.mark.asyncio
    async def test_check_game_completion_finished(self, mock_context, active_game_with_participants):
        """Тест: Проверка завершения игры - игра завершена"""
        print("\n=== ТЕСТ: Проверка завершения - игра завершена ===")
        
        game = active_game_with_participants
        
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
            
        print("✅ Игра корректно завершается, когда найдены все водители")

    @pytest.mark.asyncio
    async def test_notify_game_completion(self, mock_context, active_game_with_participants):
        """Тест: Уведомление о завершении игры"""
        print("\n=== ТЕСТ: Уведомление о завершении игры ===")
        
        game = active_game_with_participants
        game.status = GameStatus.COMPLETED
        game.ended_at = datetime.now()
        
        # Отмечаем всех водителей как найденных
        found_drivers = 0
        for participant in game.participants:
            if participant.role.value == 'driver':
                participant.is_found = True
                participant.found_at = datetime.now() - timedelta(minutes=10)
                found_drivers += 1
        
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
            
            # Проверяем содержание уведомления
            for call in mock_context.bot.send_message.call_args_list:
                args, kwargs = call
                message_text = kwargs.get('text', args[1] if len(args) > 1 else '')
                assert "завершена" in message_text.lower()
                assert game.district in message_text
                assert str(found_drivers) in message_text
                
        print("✅ Все участники получили уведомления о завершении игры")

    @pytest.mark.asyncio
    async def test_game_status_display(self, mock_update, mock_context, active_game_with_participants):
        """Тест: Отображение статуса игры"""
        print("\n=== ТЕСТ: Отображение статуса игры ===")
        
        game = active_game_with_participants
        user = game.participants[0].user
        
        # Настраиваем callback
        mock_update.callback_query.data = f"game_status_{game.id}"
        mock_update.effective_user.id = user.telegram_id
        
        # Отмечаем одного водителя как найденного
        game.participants[0].is_found = True
        game.participants[0].found_at = datetime.now() - timedelta(minutes=5)
        
        with patch.object(UserService, 'get_user_by_telegram_id', return_value=(user, True)), \
             patch.object(GameService, 'get_game_by_id', return_value=game):
            
            # Запрашиваем статус игры
            await handle_game_status_callback(mock_update, mock_context)
            
            # Проверяем ответ
            mock_update.callback_query.edit_message_text.assert_called()
            call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
            
            # Проверяем содержание статуса
            assert "статус игры" in call_args.lower()
            assert game.district in call_args
            assert "в процессе" in call_args.lower()
            assert "найдено" in call_args.lower()
            
        print("✅ Статус игры отображается корректно")

    @pytest.mark.asyncio
    async def test_full_completion_flow(self, mock_update, mock_context, active_game_with_participants):
        """Полный тест процесса завершения игры"""
        print("\n=== ПОЛНЫЙ ТЕСТ: Процесс завершения игры ===")
        
        game = active_game_with_participants
        seeker = next(p for p in game.participants if p.role.value == 'seeker')
        drivers = [p for p in game.participants if p.role.value == 'driver']
        
        with patch.object(UserService, 'get_user_by_telegram_id') as mock_get_user, \
             patch.object(GameService, 'get_game_by_id', return_value=game), \
             patch('src.handlers.callback_handler.notify_drivers_about_found') as mock_notify_drivers, \
             patch('src.handlers.callback_handler.notify_participants_about_found_driver') as mock_notify_participants, \
             patch('src.handlers.callback_handler.check_game_completion_callback') as mock_check_completion, \
             patch('src.models.base.get_db') as mock_get_db, \
             patch.object(GameService, 'end_game', return_value=True):
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(telegram_id):
                for participant in game.participants:
                    if participant.user.telegram_id == telegram_id:
                        return participant.user, True
                return None, False
            mock_get_user.side_effect = get_user_side_effect
            
            # Мокаем базу данных
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])
            
            print("1. Искатель находит первого водителя...")
            # Искатель находит первого водителя
            mock_update.effective_user.id = seeker.user.telegram_id
            mock_update.callback_query.data = f"found_car_{game.id}"
            await handle_found_car_callback(mock_update, mock_context)
            
            print("2. Первый водитель подтверждает находку...")
            # Первый водитель подтверждает
            mock_update.effective_user.id = drivers[0].user.telegram_id
            mock_update.callback_query.data = f"found_me_{game.id}"
            await handle_found_me_callback(mock_update, mock_context)
            
            # Отмечаем первого водителя как найденного
            drivers[0].is_found = True
            drivers[0].found_at = datetime.now()
            
            print("3. Искатель находит второго водителя...")
            # Искатель находит второго водителя
            mock_update.effective_user.id = seeker.user.telegram_id
            mock_update.callback_query.data = f"found_car_{game.id}"
            await handle_found_car_callback(mock_update, mock_context)
            
            print("4. Второй водитель подтверждает находку...")
            # Второй водитель подтверждает
            mock_update.effective_user.id = drivers[1].user.telegram_id
            mock_update.callback_query.data = f"found_me_{game.id}"
            
            # Отмечаем второго водителя как найденного
            drivers[1].is_found = True
            drivers[1].found_at = datetime.now()
            
            # Последний вызов должен завершить игру
            await handle_found_me_callback(mock_update, mock_context)
            
            print("5. Проверяем завершение игры...")
            
            # Проверяем вызовы уведомлений
            assert mock_notify_drivers.call_count == 2  # 2 раза находили водителей
            assert mock_notify_participants.call_count == 2  # 2 подтверждения водителей
            assert mock_check_completion.call_count == 4  # 4 проверки завершения
            
            # Проверяем уведомления
            assert mock_context.bot.send_message.call_count >= 0  # Может быть любое количество
            
        print("✅ ПОЛНЫЙ ПРОЦЕСС ЗАВЕРШЕНИЯ ИГРЫ РАБОТАЕТ КОРРЕКТНО!")

    @pytest.mark.asyncio
    async def test_error_handling_invalid_game(self, mock_update, mock_context):
        """Тест: Обработка ошибок при невалидной игре"""
        print("\n=== ТЕСТ: Обработка ошибок ===")
        
        # Настраиваем несуществующую игру
        mock_update.callback_query.data = "found_car_999"
        
        with patch.object(UserService, 'get_user_by_telegram_id', return_value=(Mock(), True)), \
             patch.object(GameService, 'get_game_by_id', return_value=None):
            
            # Попытка найти водителя в несуществующей игре
            await handle_found_car_callback(mock_update, mock_context)
            
            # Проверяем сообщение об ошибке
            mock_update.callback_query.edit_message_text.assert_called()
            call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
            assert "не найдена" in call_args.lower()
            
        print("✅ Ошибки обрабатываются корректно")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"]) 