#!/usr/bin/env python3
"""
Тест контекстных клавиатур PRYTON v2 Этап 1.4
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Тест импортов новых модулей"""
    print("🧪 Тестирование импортов новых модулей...")
    
    try:
        from src.services.user_context_service import UserContextService, UserGameContext
        print("✅ UserContextService импортирован успешно")
    except ImportError as e:
        print(f"❌ Ошибка импорта UserContextService: {e}")
        return False
    
    try:
        from src.services.dynamic_keyboard_service import DynamicKeyboardService
        print("✅ DynamicKeyboardService импортирован успешно")
    except ImportError as e:
        print(f"❌ Ошибка импорта DynamicKeyboardService: {e}")
        return False
    
    try:
        from src.handlers.contextual_actions import (
            handle_my_game_button,
            handle_game_status_button,
            handle_send_location_button,
            handle_game_results_button
        )
        print("✅ Контекстные обработчики импортированы успешно")
    except ImportError as e:
        print(f"❌ Ошибка импорта контекстных обработчиков: {e}")
        return False
    
    try:
        from src.keyboards.reply import get_contextual_main_keyboard
        print("✅ Контекстные клавиатуры импортированы успешно")
    except ImportError as e:
        print(f"❌ Ошибка импорта контекстных клавиатур: {e}")
        return False
    
    return True

def test_context_service():
    """Тест UserContextService без БД"""
    print("\n🧪 Тестирование UserContextService...")
    
    try:
        from src.services.user_context_service import UserContextService
        
        # Тест с несуществующим пользователем - должен вернуть STATUS_NORMAL
        context = UserContextService.get_user_game_context(999999)
        if context.status == UserContextService.STATUS_NORMAL:
            print("✅ get_user_game_context возвращает STATUS_NORMAL для несуществующего пользователя")
        else:
            print(f"❌ Неожиданный статус: {context.status}")
            return False
            
        print(f"✅ UserGameContext создан: {context}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в UserContextService: {e}")
        return False

def test_keyboard_service():
    """Тест DynamicKeyboardService без БД"""
    print("\n🧪 Тестирование DynamicKeyboardService...")
    
    try:
        from src.services.dynamic_keyboard_service import DynamicKeyboardService
        
        # Тест создания клавиатуры для несуществующего пользователя
        keyboard = DynamicKeyboardService.get_contextual_main_keyboard(999999)
        
        if keyboard and hasattr(keyboard, 'keyboard'):
            print("✅ get_contextual_main_keyboard создает клавиатуру")
            print(f"   Количество рядов кнопок: {len(keyboard.keyboard)}")
            
            # Проверяем, что есть кнопка "🏠 Главное меню"
            found_main_menu = False
            for row in keyboard.keyboard:
                for button in row:
                    if "Главное меню" in button.text:
                        found_main_menu = True
                        break
            
            if found_main_menu:
                print("✅ Кнопка 'Главное меню' найдена в клавиатуре")
            else:
                print("❌ Кнопка 'Главное меню' не найдена")
                return False
                
            return True
        else:
            print("❌ Клавиатура не создана")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка в DynamicKeyboardService: {e}")
        return False

def test_keyboard_integration():
    """Тест интеграции с reply keyboards"""
    print("\n🧪 Тестирование интеграции клавиатур...")
    
    try:
        from src.keyboards.reply import get_contextual_main_keyboard
        
        # Тест получения контекстной клавиатуры
        keyboard = get_contextual_main_keyboard(999999)
        
        if keyboard:
            print("✅ get_contextual_main_keyboard работает")
            return True
        else:
            print("❌ get_contextual_main_keyboard вернула None")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка в интеграции клавиатур: {e}")
        return False

def test_status_constants():
    """Тест констант статусов"""
    print("\n🧪 Тестирование констант статусов...")
    
    try:
        from src.services.user_context_service import UserContextService
        
        expected_statuses = ["normal", "registered", "in_game", "game_finished"]
        actual_statuses = [
            UserContextService.STATUS_NORMAL,
            UserContextService.STATUS_REGISTERED,
            UserContextService.STATUS_IN_GAME,
            UserContextService.STATUS_GAME_FINISHED
        ]
        
        if actual_statuses == expected_statuses:
            print("✅ Все константы статусов определены правильно")
            return True
        else:
            print(f"❌ Неожиданные константы: {actual_statuses}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при проверке констант: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 ТЕСТИРОВАНИЕ КОНТЕКСТНЫХ КЛАВИАТУР PRYTON v2")
    print("=" * 60)
    
    tests = [
        ("Импорты модулей", test_imports),
        ("UserContextService", test_context_service),
        ("DynamicKeyboardService", test_keyboard_service),
        ("Интеграция клавиатур", test_keyboard_integration),
        ("Константы статусов", test_status_constants)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - ПРОЙДЕН")
            else:
                print(f"❌ {test_name} - ПРОВАЛЕН")
        except Exception as e:
            print(f"❌ {test_name} - ОШИБКА: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 РЕЗУЛЬТАТЫ: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("\n✅ Этап 1.4 'Контекстные клавиатуры' готов к интеграции")
        return True
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 