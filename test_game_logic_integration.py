#!/usr/bin/env python3
"""
Тест для проверки интеграции логики завершения игры
с функциями добавления/удаления участников
"""
import sys
import os
sys.path.append('/d/tg_bot/pryaton')

from datetime import datetime, timedelta
from src.models.base import init_db, get_db
from src.models.game import Game, GameStatus, GameParticipant, GameRole
from src.models.user import User
from src.services.game_service import GameService
from src.services.manual_game_control_service import ManualGameControlService
from src.services.user_service import UserService

def setup_test_data():
    """Создаем тестовые данные"""
    print("🔧 Создание тестовых данных...")
    
    db_generator = get_db()
    db = next(db_generator)
    
    try:
        # Создаем тестовых пользователей
        test_users = []
        for i in range(5):
            user = User(
                telegram_id=f"test_user_{i}",
                name=f"Тестовый пользователь {i+1}",
                phone=f"+7900000000{i}",
                district="Тестовый район"
            )
            db.add(user)
            test_users.append(user)
        
        # Создаем администратора
        admin = User(
            telegram_id="admin_test",
            name="Администратор",
            phone="+79000000099",
            district="Админский район",
            is_admin=True
        )
        db.add(admin)
        
        db.commit()
        
        # Создаем тестовую игру
        game = Game(
            district="Тестовый район",
            max_participants=4,
            max_drivers=2,
            scheduled_at=datetime.now() + timedelta(hours=1),
            creator_id=admin.id,
            status=GameStatus.RECRUITING
        )
        db.add(game)
        db.commit()
        
        return game.id, admin.id, [u.id for u in test_users]
        
    finally:
        db.close()

def test_participant_addition_logic():
    """Тест логики добавления участников"""
    print("\n🧪 === ТЕСТ ДОБАВЛЕНИЯ УЧАСТНИКОВ ===")
    
    game_id, admin_id, user_ids = setup_test_data()
    
    # Добавляем участников
    for i, user_id in enumerate(user_ids[:3]):
        result = ManualGameControlService.add_participant_to_game(game_id, user_id, admin_id)
        print(f"• Добавление участника {i+1}: {'✅' if result['success'] else '❌'} {result.get('message', result.get('error'))}")
    
    # Проверяем роли
    control_info = ManualGameControlService.get_game_control_info(game_id)
    if control_info["success"]:
        participants = control_info["participants"]
        drivers = [p for p in participants if p["role"] == "driver"]
        seekers = [p for p in participants if p["role"] == "seeker"]
        
        print(f"📊 Результат:")
        print(f"   • Водителей: {len(drivers)}")
        print(f"   • Искателей: {len(seekers)}")
        print(f"   • Без роли: {len([p for p in participants if not p['role']])}")
        
        if len(drivers) == 2 and len(seekers) == 1:
            print("✅ Роли назначены корректно!")
        else:
            print("❌ Проблема с назначением ролей!")
    
    return game_id, admin_id, user_ids

def test_game_completion_logic():
    """Тест логики завершения игры"""
    print("\n🧪 === ТЕСТ ЛОГИКИ ЗАВЕРШЕНИЯ ИГРЫ ===")
    
    game_id, admin_id, user_ids = test_participant_addition_logic()
    
    # Запускаем игру
    print("🚀 Запуск игры...")
    start_result = ManualGameControlService.manual_start_hiding_phase(game_id, admin_id)
    print(f"   Начало игры: {'✅' if start_result['success'] else '❌'}")
    
    # Переходим к поиску
    search_result = ManualGameControlService.manual_start_searching_phase(game_id, admin_id)
    print(f"   Фаза поиска: {'✅' if search_result['success'] else '❌'}")
    
    # Получаем участников
    control_info = ManualGameControlService.get_game_control_info(game_id)
    if not control_info["success"]:
        print("❌ Не удалось получить информацию об игре")
        return
    
    participants = control_info["participants"]
    drivers = [p for p in participants if p["role"] == "driver"]
    
    if len(drivers) < 2:
        print("❌ Недостаточно водителей для теста")
        return
    
    # Отмечаем первого водителя как найденного
    print("🔍 Отмечаем первого водителя как найденного...")
    mark_result1 = ManualGameControlService.manual_mark_participant_found(
        game_id, drivers[0]["id"], admin_id
    )
    print(f"   Первый водитель: {'✅' if mark_result1['success'] else '❌'}")
    
    # Проверяем статус игры
    game_info = ManualGameControlService.get_game_control_info(game_id)
    if game_info["success"]:
        game_status = game_info["game"]["status"]
        print(f"   Статус игры: {game_status}")
        
        if game_status != "completed":
            print("✅ Игра продолжается (корректно)")
        else:
            print("❌ Игра завершилась раньше времени!")
    
    # Отмечаем второго водителя как найденного
    print("🔍 Отмечаем второго водителя как найденного...")
    mark_result2 = ManualGameControlService.manual_mark_participant_found(
        game_id, drivers[1]["id"], admin_id
    )
    print(f"   Второй водитель: {'✅' if mark_result2['success'] else '❌'}")
    
    # Проверяем завершение игры
    game_info = ManualGameControlService.get_game_control_info(game_id)
    if game_info["success"]:
        game_status = game_info["game"]["status"]
        print(f"   Статус игры: {game_status}")
        
        if game_status == "completed":
            print("✅ Игра автоматически завершена!")
        else:
            print("❌ Игра не завершилась автоматически!")
    
    return game_id, admin_id, drivers

def test_participant_removal_logic():
    """Тест логики удаления участников"""
    print("\n🧪 === ТЕСТ УДАЛЕНИЯ УЧАСТНИКОВ ===")
    
    game_id, admin_id, drivers = test_game_completion_logic()
    
    # Отменяем отметку одного водителя
    print("🔄 Отменяем отметку найденного у первого водителя...")
    unmark_result = ManualGameControlService.manual_unmark_participant_found(
        game_id, drivers[0]["id"], admin_id
    )
    print(f"   Отмена отметки: {'✅' if unmark_result['success'] else '❌'}")
    
    # Проверяем, что игра возобновилась
    game_info = ManualGameControlService.get_game_control_info(game_id)
    if game_info["success"]:
        game_status = game_info["game"]["status"]
        print(f"   Статус игры: {game_status}")
        
        if game_status in ["hiding_phase", "searching_phase"]:
            print("✅ Игра возобновлена!")
        else:
            print("❌ Игра не возобновилась!")
    
    # Удаляем найденного водителя
    print("🗑️ Удаляем найденного водителя...")
    remove_result = ManualGameControlService.remove_participant_from_game(
        game_id, drivers[1]["id"], admin_id
    )
    print(f"   Удаление: {'✅' if remove_result['success'] else '❌'}")
    
    # Проверяем финальное состояние
    final_info = ManualGameControlService.get_game_control_info(game_id)
    if final_info["success"]:
        final_participants = final_info["participants"]
        final_drivers = [p for p in final_participants if p["role"] == "driver"]
        game_status = final_info["game"]["status"]
        
        print(f"📊 Финальное состояние:")
        print(f"   • Водителей осталось: {len(final_drivers)}")
        print(f"   • Статус игры: {game_status}")
        
        if len(final_drivers) == 1 and game_status in ["hiding_phase", "searching_phase"]:
            print("✅ Логика корректна - игра продолжается с одним водителем!")
        else:
            print("❌ Проблема с логикой после удаления!")

def main():
    """Основная функция теста"""
    print("🎮 === ТЕСТ ИНТЕГРАЦИИ ЛОГИКИ ИГРЫ ===")
    print("Проверяем корректность работы логики завершения игры")
    print("при добавлении/удалении участников и изменении их статуса")
    print()
    
    try:
        # Инициализируем БД
        init_db()
        
        # Запускаем тесты
        test_participant_removal_logic()
        
        print("\n✅ === ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ ===")
        print("Проверьте результаты выше для выявления проблем")
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 