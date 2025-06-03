import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram.ext import Application

from src.services.scheduler_service import SchedulerService
from src.services.game_service import GameService
from src.services.user_service import UserService
from src.models.game import Game, GameStatus, GameRole, GameParticipant
from src.models.user import User as UserModel, UserRole


class TestSchedulerNotifications:
    """Тесты системы планировщика и уведомлений"""
    
    @pytest.fixture
    def mock_application(self):
        """Создание мок-приложения Telegram"""
        app = Mock(spec=Application)
        app.bot = Mock()
        app.bot.send_message = AsyncMock()
        return app
    
    @pytest.fixture
    def scheduler_service(self, mock_application):
        """Создание экземпляра SchedulerService"""
        return SchedulerService(mock_application)
    
    @pytest.fixture
    def test_game_future(self):
        """Создание тестовой игры в будущем"""
        future_time = datetime.now() + timedelta(hours=2)
        
        game = Mock()
        game.id = 1
        game.district = "Центральный"
        game.scheduled_at = future_time
        game.started_at = None
        game.max_participants = 6
        game.max_drivers = 2
        game.status = GameStatus.RECRUITING
        game.description = "Тестовая игра"
        
        # Создаем участников
        participants = []
        for i in range(4):
            participant = Mock()
            participant.user_id = i + 1
            participant.game_id = game.id
            participant.role = GameRole.DRIVER if i < 2 else GameRole.SEEKER
            participant.user = Mock()
            participant.user.name = f"Игрок {i + 1}"
            participant.user.telegram_id = 10000 + i
            participants.append(participant)
        
        game.participants = participants
        return game
    
    @pytest.fixture
    def test_game_active(self):
        """Создание активной тестовой игры"""
        start_time = datetime.now() - timedelta(minutes=15)
        
        game = Mock()
        game.id = 2
        game.district = "Северный"
        game.scheduled_at = start_time
        game.started_at = start_time
        game.max_participants = 4
        game.max_drivers = 1
        game.status = GameStatus.HIDING_PHASE
        game.description = "Активная игра"
        
        # Создаем участников
        participants = []
        for i in range(4):
            participant = Mock()
            participant.user_id = i + 1
            participant.game_id = game.id
            participant.role = GameRole.DRIVER if i == 0 else GameRole.SEEKER
            participant.is_found = False
            participant.user = Mock()
            participant.user.name = f"Игрок {i + 1}"
            participant.user.telegram_id = 20000 + i
            participants.append(participant)
        
        game.participants = participants
        return game

    def test_scheduler_initialization(self, mock_application):
        """Тест: Инициализация планировщика"""
        print("\n=== ТЕСТ: Инициализация планировщика ===")
        
        scheduler = SchedulerService(mock_application)
        
        # Проверяем инициализацию
        assert scheduler.application == mock_application
        assert scheduler.bot == mock_application.bot
        assert scheduler.hiding_time == 30  # значение по умолчанию
        assert scheduler.reminder_times == [60, 24, 5]  # значения по умолчанию
        
        print("✅ Планировщик успешно инициализирован")

    def test_scheduler_start_stop(self, scheduler_service):
        """Тест: Проверка методов запуска и остановки планировщика"""
        print("\n=== ТЕСТ: Методы планировщика ===")
        
        # Проверяем, что методы существуют и можно их вызвать
        assert hasattr(scheduler_service, 'start'), "Метод start должен существовать"
        assert hasattr(scheduler_service, 'shutdown'), "Метод shutdown должен существовать"
        assert hasattr(scheduler_service.scheduler, 'start'), "Метод scheduler.start должен существовать"
        assert hasattr(scheduler_service.scheduler, 'shutdown'), "Метод scheduler.shutdown должен существовать"
        
        print("✅ Все методы планировщика доступны")

    @pytest.mark.asyncio
    async def test_send_game_reminder_60_minutes(self, scheduler_service, test_game_future):
        """Тест: Отправка напоминания за 60 минут"""
        print("\n=== ТЕСТ: Напоминание за 60 минут ===")
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_future), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                user = Mock()
                user.telegram_id = 10000 + user_id - 1
                user.name = f"Игрок {user_id}"
                return user, True
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем напоминание
            await scheduler_service.send_game_reminder(test_game_future.id, 60)
            
            # Проверяем количество отправленных сообщений
            assert scheduler_service.bot.send_message.call_count == len(test_game_future.participants)
            
            # Проверяем содержание напоминания
            for call in scheduler_service.bot.send_message.call_args_list:
                args, kwargs = call
                message_text = kwargs.get('text', args[1] if len(args) > 1 else '')
                assert "Напоминание о игре" in message_text
                assert "1 час" in message_text
                assert test_game_future.district in message_text
                
        print("✅ Напоминание за 60 минут отправлено корректно")

    @pytest.mark.asyncio
    async def test_send_game_reminder_24_hours(self, scheduler_service, test_game_future):
        """Тест: Отправка напоминания за 24 часа"""
        print("\n=== ТЕСТ: Напоминание за 24 часа ===")
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_future), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                user = Mock()
                user.telegram_id = 10000 + user_id - 1
                user.name = f"Игрок {user_id}"
                return user, True
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем напоминание за 24 часа (1440 минут)
            await scheduler_service.send_game_reminder(test_game_future.id, 1440)
            
            # Проверяем количество отправленных сообщений
            assert scheduler_service.bot.send_message.call_count == len(test_game_future.participants)
            
            # Проверяем содержание напоминания
            for call in scheduler_service.bot.send_message.call_args_list:
                args, kwargs = call
                message_text = kwargs.get('text', args[1] if len(args) > 1 else '')
                assert "Напоминание о игре" in message_text
                assert "24 час" in message_text
                
        print("✅ Напоминание за 24 часа отправлено корректно")

    @pytest.mark.asyncio
    async def test_send_game_reminder_5_minutes(self, scheduler_service, test_game_future):
        """Тест: Отправка напоминания за 5 минут"""
        print("\n=== ТЕСТ: Напоминание за 5 минут ===")
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_future), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                user = Mock()
                user.telegram_id = 10000 + user_id - 1
                user.name = f"Игрок {user_id}"
                return user, True
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем напоминание за 5 минут
            await scheduler_service.send_game_reminder(test_game_future.id, 5)
            
            # Проверяем количество отправленных сообщений
            assert scheduler_service.bot.send_message.call_count == len(test_game_future.participants)
            
            # Проверяем содержание напоминания
            for call in scheduler_service.bot.send_message.call_args_list:
                args, kwargs = call
                message_text = kwargs.get('text', args[1] if len(args) > 1 else '')
                assert "Напоминание о игре" in message_text
                assert "5 минут" in message_text
                
        print("✅ Напоминание за 5 минут отправлено корректно")

    @pytest.mark.asyncio
    async def test_notify_game_started(self, scheduler_service, test_game_active):
        """Тест: Уведомление о начале игры"""
        print("\n=== ТЕСТ: Уведомление о начале игры ===")
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_active), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                user = Mock()
                user.telegram_id = 20000 + user_id - 1
                user.name = f"Игрок {user_id}"
                return user, True
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем уведомление о начале игры
            await scheduler_service.notify_game_started(test_game_active.id)
            
            # Проверяем количество отправленных сообщений
            assert scheduler_service.bot.send_message.call_count == len(test_game_active.participants)
            
            # Проверяем содержание уведомлений для водителей и искателей
            driver_messages = []
            seeker_messages = []
            
            for i, call in enumerate(scheduler_service.bot.send_message.call_args_list):
                args, kwargs = call
                message_text = kwargs.get('text', args[1] if len(args) > 1 else '')
                
                if i == 0:  # Первый участник - водитель
                    driver_messages.append(message_text)
                    assert "Водитель" in message_text
                    assert "спрятаться" in message_text
                else:  # Остальные - искатели
                    seeker_messages.append(message_text)
                    assert "Искатель" in message_text
                    assert ("Поиск" in message_text or "поиск" in message_text)
                
        print("✅ Уведомления о начале игры отправлены корректно")

    @pytest.mark.asyncio
    async def test_notify_game_cancelled(self, scheduler_service, test_game_future):
        """Тест: Уведомление об отмене игры"""
        print("\n=== ТЕСТ: Уведомление об отмене игры ===")
        
        cancellation_reason = "Недостаточно участников"
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_future), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                user = Mock()
                user.telegram_id = 10000 + user_id - 1
                user.name = f"Игрок {user_id}"
                return user, True
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем уведомление об отмене
            await scheduler_service.notify_game_cancelled(test_game_future.id, cancellation_reason)
            
            # Проверяем количество отправленных сообщений
            assert scheduler_service.bot.send_message.call_count == len(test_game_future.participants)
            
            # Проверяем содержание уведомлений
            for call in scheduler_service.bot.send_message.call_args_list:
                args, kwargs = call
                message_text = kwargs.get('text', args[1] if len(args) > 1 else '')
                assert "отменена" in message_text.lower()
                assert cancellation_reason in message_text
                assert test_game_future.district in message_text
                
        print("✅ Уведомления об отмене игры отправлены корректно")

    @pytest.mark.asyncio
    async def test_end_hiding_phase(self, scheduler_service, test_game_active):
        """Тест: Завершение фазы прятки"""
        print("\n=== ТЕСТ: Завершение фазы прятки ===")
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_active), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                user = Mock()
                user.telegram_id = 20000 + user_id - 1
                user.name = f"Игрок {user_id}"
                return user, True
            mock_get_user.side_effect = get_user_side_effect
            
            # Завершаем фазу прятки
            await scheduler_service.end_hiding_phase(test_game_active.id)
            
            # Проверяем количество отправленных сообщений
            assert scheduler_service.bot.send_message.call_count == len(test_game_active.participants)
            
            # Проверяем содержание уведомлений
            for i, call in enumerate(scheduler_service.bot.send_message.call_args_list):
                args, kwargs = call
                message_text = kwargs.get('text', args[1] if len(args) > 1 else '')
                
                assert "Время прятки истекло" in message_text
                
                if i == 0:  # Водитель
                    assert "Водители" in message_text
                    assert "закончилось" in message_text
                else:  # Искатели
                    assert "Искатели" in message_text
                    assert "Начинайте поиск" in message_text
                
        print("✅ Уведомления о завершении фазы прятки отправлены корректно")

    @pytest.mark.asyncio
    async def test_auto_start_game_success(self, scheduler_service, test_game_future):
        """Тест: Автоматический запуск игры при достаточном количестве участников"""
        print("\n=== ТЕСТ: Автоматический запуск игры ===")
        
        # Меняем статус игры на UPCOMING
        test_game_future.status = GameStatus.UPCOMING
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_future), \
             patch.object(GameService, 'assign_roles', return_value=[(1, GameRole.DRIVER), (2, GameRole.SEEKER)]), \
             patch.object(GameService, 'start_game', return_value=True), \
             patch.object(scheduler_service, 'notify_game_started') as mock_notify:
            
            # Автоматически запускаем игру
            await scheduler_service.start_game(test_game_future.id)
            
            # Проверяем распределение ролей и запуск
            GameService.assign_roles.assert_called_once_with(test_game_future.id)
            GameService.start_game.assert_called_once_with(test_game_future.id)
            mock_notify.assert_called_once_with(test_game_future.id)
            
        print("✅ Игра автоматически запущена при достаточном количестве участников")

    @pytest.mark.asyncio
    async def test_auto_start_game_insufficient_participants(self, scheduler_service, test_game_future):
        """Тест: Автоматическая отмена игры при недостатке участников"""
        print("\n=== ТЕСТ: Автоматическая отмена при недостатке участников ===")
        
        # Убираем участников
        test_game_future.participants = [test_game_future.participants[0]]  # Только 1 участник
        test_game_future.status = GameStatus.UPCOMING
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_future), \
             patch.object(GameService, 'cancel_game', return_value=True), \
             patch.object(scheduler_service, 'notify_game_cancelled') as mock_notify_cancel:
            
            # Пытаемся автоматически запустить игру
            await scheduler_service.start_game(test_game_future.id)
            
            # Проверяем отмену игры
            GameService.cancel_game.assert_called_once_with(test_game_future.id)
            mock_notify_cancel.assert_called_once_with(test_game_future.id, "Недостаточно участников")
            
        print("✅ Игра автоматически отменена при недостатке участников")

    def test_schedule_game_reminders(self, scheduler_service, test_game_future):
        """Тест: Планирование напоминаний для игры"""
        print("\n=== ТЕСТ: Планирование напоминаний ===")
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_future), \
             patch.object(scheduler_service.scheduler, 'add_job') as mock_add_job:
            
            # Планируем напоминания
            scheduler_service.schedule_game_reminders(test_game_future.id)
            
            # Проверяем количество запланированных задач
            # 3 напоминания + 1 автостарт + 1 завершение прятки = 5 задач
            assert mock_add_job.call_count == 5
            
            # Проверяем типы запланированных задач
            job_ids = [call[1]['id'] for call in mock_add_job.call_args_list]
            
            # Напоминания
            assert f"reminder_{test_game_future.id}_60min" in job_ids
            assert f"reminder_{test_game_future.id}_24min" in job_ids
            assert f"reminder_{test_game_future.id}_5min" in job_ids
            
            # Автостарт
            assert f"start_game_{test_game_future.id}" in job_ids
            
            # Завершение прятки
            assert f"hiding_end_{test_game_future.id}" in job_ids
            
        print("✅ Напоминания и задачи запланированы корректно")

    def test_cancel_game_jobs(self, scheduler_service):
        """Тест: Отмена задач для игры"""
        print("\n=== ТЕСТ: Отмена задач игры ===")
        
        game_id = 1
        
        # Создаем мок-задачи
        mock_jobs = []
        for i in range(5):
            job = Mock()
            job.id = f"test_job_{game_id}_{i}"
            mock_jobs.append(job)
        
        # Добавляем задачи других игр
        other_job = Mock()
        other_job.id = "test_job_2_0"
        mock_jobs.append(other_job)
        
        with patch.object(scheduler_service.scheduler, 'get_jobs', return_value=mock_jobs), \
             patch.object(scheduler_service.scheduler, 'remove_job') as mock_remove_job:
            
            # Отменяем задачи для игры
            scheduler_service.cancel_game_jobs(game_id)
            
            # Проверяем, что удалены только задачи для нужной игры
            assert mock_remove_job.call_count == 5  # Только задачи с game_id=1
            
            removed_job_ids = [call[0][0] for call in mock_remove_job.call_args_list]
            for job_id in removed_job_ids:
                assert str(game_id) in job_id
                
        print("✅ Задачи игры корректно отменены")

    @pytest.mark.asyncio
    async def test_notification_error_handling(self, scheduler_service, test_game_future):
        """Тест: Обработка ошибок при отправке уведомлений"""
        print("\n=== ТЕСТ: Обработка ошибок уведомлений ===")
        
        # Настраиваем ошибку при отправке сообщения одному пользователю
        async def send_message_side_effect(chat_id, text, **kwargs):
            if chat_id == 10000:  # Первый пользователь
                raise Exception("Пользователь заблокировал бота")
            return Mock()
        
        scheduler_service.bot.send_message.side_effect = send_message_side_effect
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_future), \
             patch.object(UserService, 'get_user_by_id') as mock_get_user:
            
            # Настраиваем возврат пользователей
            def get_user_side_effect(user_id):
                user = Mock()
                user.telegram_id = 10000 + user_id - 1
                user.name = f"Игрок {user_id}"
                return user, True
            mock_get_user.side_effect = get_user_side_effect
            
            # Отправляем напоминание (не должно упасть с ошибкой)
            await scheduler_service.send_game_reminder(test_game_future.id, 60)
            
            # Проверяем, что попытки отправки были сделаны всем участникам
            assert scheduler_service.bot.send_message.call_count == len(test_game_future.participants)
            
        print("✅ Ошибки при отправке уведомлений обрабатываются корректно")

    @pytest.mark.asyncio
    async def test_reminder_cancelled_game(self, scheduler_service, test_game_future):
        """Тест: Напоминание для отмененной игры"""
        print("\n=== ТЕСТ: Напоминание для отмененной игры ===")
        
        # Меняем статус игры на отмененную
        test_game_future.status = GameStatus.CANCELED
        
        with patch.object(GameService, 'get_game_by_id', return_value=test_game_future):
            
            # Пытаемся отправить напоминание
            await scheduler_service.send_game_reminder(test_game_future.id, 60)
            
            # Проверяем, что уведомления НЕ отправлены
            scheduler_service.bot.send_message.assert_not_called()
            
        print("✅ Напоминания для отмененных игр корректно пропускаются")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"]) 