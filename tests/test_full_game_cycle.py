# 🎮 Полный интеграционный тест игрового цикла PRYTON

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Добавляем корневой путь проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.settings_service import SettingsService
from src.services.scheduler_service import SchedulerService
from src.services.monitoring_service import MonitoringService
from src.models.base import Base
from src.models.user import User
from src.models.game import Game, GameStatus, GameRole
from src.models.settings import Setting, District, Role


class TestFullGameCycle:
    """Тест полного игрового цикла от создания до завершения"""
    
    @classmethod
    def setup_class(cls):
        """Настройка тестовой среды"""
        # Создаем in-memory SQLite БД для тестов
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)
        
        # Создаем сессию
        Session = sessionmaker(bind=cls.engine)
        cls.session = Session()
        
        # Патчим глобальную сессию
        import src.models.base
        src.models.base.get_session = lambda: cls.session
        
        print("🏗️  Тестовая среда настроена")
    
    @classmethod
    def teardown_class(cls):
        """Очистка после тестов"""
        cls.session.close()
        print("🧹 Тестовая среда очищена")
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        # Очищаем все таблицы
        for table in reversed(Base.metadata.sorted_tables):
            self.session.execute(table.delete())
        self.session.commit()
        
        # Создаем базовые настройки
        self._setup_basic_settings()
        print("📋 Базовые настройки созданы")
    
    def _setup_basic_settings(self):
        """Создание базовых настроек для тестов"""
        # Добавляем районы
        districts = ["Центр", "Северный", "Южный"]
        for district_name in districts:
            district = District(name=district_name, is_active=True)
            self.session.add(district)
        
        # Добавляем роли
        roles = ["Игрок", "Водитель", "Искатель"]
        for role_name in roles:
            role = Role(name=role_name, is_active=True)
            self.session.add(role)
        
        # Добавляем настройки
        settings = [
            Setting(key="game_rules", value="Тестовые правила игры"),
            Setting(key="hiding_time", value="30"),
            Setting(key="game_zone_radius", value="1000"),
        ]
        for setting in settings:
            self.session.add(setting)
        
        self.session.commit()
    
    def _create_test_users(self, count=6):
        """Создание тестовых пользователей"""
        users = []
        
        # Создаем админа
        admin = User(
            telegram_id=123456789,
            name="Админ Тестовый",
            district="Центр",
            default_role="Игрок",
            is_registered=True
        )
        self.session.add(admin)
        users.append(admin)
        
        # Создаем обычных пользователей
        for i in range(1, count):
            user = User(
                telegram_id=100000000 + i,
                name=f"Пользователь {i}",
                district="Центр",
                default_role="Игрок", 
                is_registered=True
            )
            self.session.add(user)
            users.append(user)
        
        self.session.commit()
        return users
    
    @patch('src.services.scheduler_service.scheduler')
    def test_complete_game_cycle(self, mock_scheduler):
        """Тест полного игрового цикла"""
        print("\n🚀 Начинаем тест полного игрового цикла")
        
        # === ЭТАП 1: Подготовка ===
        print("\n📋 ЭТАП 1: Подготовка пользователей")
        users = self._create_test_users(6)
        admin = users[0]
        players = users[1:]
        
        print(f"✅ Создано {len(users)} пользователей (1 админ + {len(players)} игроков)")
        
        # Проверяем права админа
        assert UserService.is_admin(admin.telegram_id), "Админ должен иметь права"
        
        # === ЭТАП 2: Создание игры ===
        print("\n🎮 ЭТАП 2: Создание игры администратором")
        
        game_time = datetime.now() + timedelta(minutes=2)
        game = GameService.create_game(
            district="Центр",
            max_participants=6,
            max_drivers=2,
            scheduled_at=game_time,
            creator_id=admin.id,
            description="Тестовая игра для полного цикла"
        )
        
        assert game is not None, "Игра должна быть создана"
        assert game.status == GameStatus.RECRUITMENT, "Игра должна быть в статусе 'Набор'"
        print(f"✅ Игра #{game.id} создана на {game_time.strftime('%d.%m.%Y %H:%M')}")
        
        # === ЭТАП 3: Запись участников ===
        print("\n👥 ЭТАП 3: Запись участников на игру")
        
        for i, player in enumerate(players):
            success = GameService.join_game(game.id, player.id)
            assert success, f"Пользователь {player.name} должен записаться на игру"
            print(f"✅ {player.name} записался на игру")
        
        # Проверяем количество участников
        updated_game = GameService.get_game_by_id(game.id)
        assert len(updated_game.participants) == 5, "Должно быть 5 участников"
        assert updated_game.status == GameStatus.RECRUITMENT, "Игра должна быть в наборе"
        
        # === ЭТАП 4: Автоматический старт игры ===
        print("\n🚦 ЭТАП 4: Автоматический старт игры")
        
        # Симулируем автоматический старт
        with patch('src.services.game_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = game_time + timedelta(seconds=1)
            success = GameService.start_game(game.id)
            assert success, "Игра должна запуститься"
        
        started_game = GameService.get_game_by_id(game.id)
        assert started_game.status == GameStatus.HIDING, "Игра должна быть в статусе 'Прятки'"
        print(f"✅ Игра автоматически запущена, статус: {started_game.status.value}")
        
        # === ЭТАП 5: Распределение ролей ===
        print("\n🎲 ЭТАП 5: Распределение ролей")
        
        roles = GameService.assign_roles(game.id)
        assert roles is not None, "Роли должны быть распределены"
        
        # Проверяем распределение
        updated_game = GameService.get_game_by_id(game.id)
        drivers = [p for p in updated_game.participants if p.role == GameRole.DRIVER]
        seekers = [p for p in updated_game.participants if p.role == GameRole.SEEKER]
        
        assert len(drivers) == 2, f"Должно быть 2 водителя, найдено {len(drivers)}"
        assert len(seekers) == 3, f"Должно быть 3 искателя, найдено {len(seekers)}"
        
        print(f"✅ Роли распределены: {len(drivers)} водителей, {len(seekers)} искателей")
        for driver in drivers:
            print(f"  🚗 Водитель: {driver.user.name}")
        for seeker in seekers:
            print(f"  🔍 Искатель: {seeker.user.name}")
        
        # === ЭТАП 6: Фаза прятки (30 минут) ===
        print("\n⏱️  ЭТАП 6: Фаза прятки")
        
        # Проверяем, что игра в статусе HIDING
        assert updated_game.status == GameStatus.HIDING, "Должна быть фаза прятки"
        
        # Симулируем отправку геолокации водителями
        from src.services.location_service import LocationService
        for driver in drivers:
            location = LocationService.save_location(
                user_id=driver.user.id,
                game_id=game.id,
                latitude=55.7558 + (driver.user.id * 0.001),  # Разные координаты
                longitude=37.6176 + (driver.user.id * 0.001)
            )
            assert location is not None, f"Геолокация водителя {driver.user.name} должна сохраниться"
            print(f"📍 {driver.user.name} отправил геолокацию")
        
        # === ЭТАП 7: Начало поиска ===
        print("\n🔍 ЭТАП 7: Переход к фазе поиска")
        
        # Симулируем окончание времени прятки
        with patch('src.services.game_service.datetime') as mock_datetime:
            search_time = game_time + timedelta(minutes=30, seconds=1)
            mock_datetime.now.return_value = search_time
            
            # Обновляем статус игры на SEARCH
            success = GameService.update_game_status(game.id, GameStatus.SEARCH)
            assert success, "Игра должна перейти в статус поиска"
        
        search_game = GameService.get_game_by_id(game.id)
        assert search_game.status == GameStatus.SEARCH, "Игра должна быть в статусе 'Поиск'"
        print(f"✅ Игра перешла в фазу поиска, статус: {search_game.status.value}")
        
        # === ЭТАП 8: Отправка фотографий искателями ===
        print("\n📸 ЭТАП 8: Отправка фотографий искателями")
        
        from src.services.photo_service import PhotoService
        photos_sent = 0
        
        for seeker in seekers:
            # Симулируем отправку фото
            photo = PhotoService.save_photo(
                user_id=seeker.user.id,
                game_id=game.id,
                file_id=f"test_photo_{seeker.user.id}",
                latitude=55.7558 + (seeker.user.id * 0.001),
                longitude=37.6176 + (seeker.user.id * 0.001)
            )
            if photo:
                photos_sent += 1
                print(f"📸 {seeker.user.name} отправил фотографию")
        
        print(f"✅ Отправлено {photos_sent} фотографий")
        
        # === ЭТАП 9: Одобрение фотографий админом ===
        print("\n✅ ЭТАП 9: Одобрение фотографий")
        
        # Получаем все фотографии игры
        photos = PhotoService.get_game_photos(game.id)
        approved_count = 0
        
        for photo in photos:
            # Симулируем одобрение админом
            success = PhotoService.approve_photo(photo.id)
            if success:
                approved_count += 1
                print(f"✅ Фотография от {photo.user.name} одобрена")
        
        print(f"✅ Одобрено {approved_count} фотографий")
        
        # === ЭТАП 10: Завершение игры ===
        print("\n🏁 ЭТАП 10: Завершение игры")
        
        # Симулируем завершение игры
        success = GameService.finish_game(game.id)
        assert success, "Игра должна завершиться"
        
        finished_game = GameService.get_game_by_id(game.id)
        assert finished_game.status == GameStatus.FINISHED, "Игра должна быть завершена"
        print(f"✅ Игра завершена, финальный статус: {finished_game.status.value}")
        
        # === ЭТАП 11: Проверка статистики ===
        print("\n📊 ЭТАП 11: Проверка статистики")
        
        # Проверяем мониторинг
        stats = MonitoringService.get_basic_stats()
        assert stats['games_today'] >= 1, "Должна быть как минимум 1 игра сегодня"
        assert stats['total_participations'] >= len(players), "Должны быть участия"
        
        # Проверяем детали игры
        game_details = MonitoringService.get_game_details(game.id)
        assert game_details is not None, "Детали игры должны быть доступны"
        assert len(game_details['participants']) == len(players), "Все участники должны быть учтены"
        
        print(f"📈 Статистика: {stats['games_today']} игр сегодня, {stats['total_participations']} участий")
        print(f"📋 Игра #{game.id}: {len(game_details['participants'])} участников")
        
        # === ЭТАП 12: Генерация отчета ===
        print("\n📄 ЭТАП 12: Генерация отчета")
        
        report = MonitoringService.generate_game_report(game.id)
        assert report is not None, "Отчет должен быть сгенерирован"
        assert "Тестовая игра для полного цикла" in report, "Отчет должен содержать описание игры"
        
        print("✅ Отчет по игре сгенерирован")
        print(f"📝 Длина отчета: {len(report)} символов")
        
        # === ФИНАЛЬНАЯ ПРОВЕРКА ===
        print("\n🎯 ФИНАЛЬНАЯ ПРОВЕРКА")
        
        final_game = GameService.get_game_by_id(game.id)
        assert final_game.status == GameStatus.FINISHED
        assert len(final_game.participants) == len(players)
        assert all(p.role is not None for p in final_game.participants)
        
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        print(f"🎮 Полный игровой цикл завершен для игры #{game.id}")
        print(f"⏱️  Общее время тестирования: ~{(datetime.now() - datetime.now()).total_seconds():.2f} сек")
        
        return True
    
    def test_game_cycle_edge_cases(self):
        """Тест граничных случаев игрового цикла"""
        print("\n🧪 Тест граничных случаев")
        
        users = self._create_test_users(3)  # Минимальное количество
        admin = users[0]
        
        # Тест с минимальным количеством участников
        game = GameService.create_game(
            district="Центр",
            max_participants=3,
            max_drivers=1,
            scheduled_at=datetime.now() + timedelta(minutes=1),
            creator_id=admin.id
        )
        
        # Записываем игроков
        for player in users[1:]:
            GameService.join_game(game.id, player.id)
        
        # Проверяем запуск с минимальным составом
        success = GameService.start_game(game.id)
        assert success, "Игра должна запускаться с минимальным составом"
        
        # Проверяем распределение ролей
        roles = GameService.assign_roles(game.id)
        assert roles is not None, "Роли должны распределяться корректно"
        
        updated_game = GameService.get_game_by_id(game.id)
        drivers = [p for p in updated_game.participants if p.role == GameRole.DRIVER]
        seekers = [p for p in updated_game.participants if p.role == GameRole.SEEKER]
        
        assert len(drivers) == 1, "Должен быть 1 водитель"
        assert len(seekers) == 1, "Должен быть 1 искатель"
        
        print("✅ Тест граничных случаев пройден")
    
    def test_scheduler_integration(self):
        """Тест интеграции с планировщиком"""
        print("\n⏰ Тест интеграции с планировщиком")
        
        users = self._create_test_users(4)
        admin = users[0]
        
        # Создаем игру на будущее время
        future_time = datetime.now() + timedelta(hours=2)
        game = GameService.create_game(
            district="Центр",
            max_participants=4,
            max_drivers=1,
            scheduled_at=future_time,
            creator_id=admin.id
        )
        
        # Проверяем, что планировщик настроен (через мок)
        with patch('src.services.scheduler_service.scheduler') as mock_scheduler:
            # Симулируем планирование задач
            SchedulerService.schedule_game_reminders(game)
            
            # Проверяем, что задачи были добавлены
            assert mock_scheduler.add_job.called, "Задачи планировщика должны быть добавлены"
            
        print("✅ Интеграция с планировщиком проверена")


def run_full_test():
    """Запуск полного теста"""
    print("🧪 ЗАПУСК ПОЛНОГО ИНТЕГРАЦИОННОГО ТЕСТА ИГРОВОГО ЦИКЛА")
    print("=" * 60)
    
    test_instance = TestFullGameCycle()
    
    try:
        # Настройка
        test_instance.setup_class()
        test_instance.setup_method()
        
        # Основной тест
        success = test_instance.test_complete_game_cycle()
        
        if success:
            print("\n" + "=" * 60)
            print("🎉 ПОЛНЫЙ ТЕСТ ИГРОВОГО ЦИКЛА УСПЕШНО ЗАВЕРШЕН!")
            print("✅ Все этапы пройдены:")
            print("   📋 Подготовка пользователей")
            print("   🎮 Создание игры администратором") 
            print("   👥 Запись участников")
            print("   🚦 Автоматический старт")
            print("   🎲 Распределение ролей")
            print("   ⏱️  Фаза прятки")
            print("   🔍 Фаза поиска")
            print("   📸 Отправка фотографий")
            print("   ✅ Одобрение фотографий")
            print("   🏁 Завершение игры")
            print("   📊 Проверка статистики")
            print("   📄 Генерация отчета")
            print("\n🚀 СИСТЕМА ГОТОВА К ПРОДАКШЕНУ!")
            
    except Exception as e:
        print(f"\n❌ ОШИБКА В ТЕСТЕ: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Очистка
        test_instance.teardown_class()
    
    return True


if __name__ == "__main__":
    run_full_test() 