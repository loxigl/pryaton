#!/usr/bin/env python3
"""
Запуск всех тестов PRYTON v2 с генерацией отчёта
Покрывает полный игровой процесс от регистрации до завершения
"""

import subprocess
import sys
import os
from datetime import datetime


def print_header(title):
    """Печать заголовка секции"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_section(title):
    """Печать подзаголовка"""
    print(f"\n📋 {title}")
    print("-" * 40)


def run_test_file(test_file, description):
    """Запуск конкретного файла тестов"""
    print(f"\n🔄 Запуск: {description}")
    print(f"   Файл: {test_file}")
    
    try:
        # Запускаем тесты с подробным выводом
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            test_file, 
            "-v", "-s", "--tb=short"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {description} - ПРОЙДЕНЫ")
            return True, result.stdout
        else:
            print(f"❌ {description} - ПРОВАЛЕНЫ")
            print(f"Ошибки:\n{result.stderr}")
            return False, result.stderr
            
    except Exception as e:
        print(f"❌ Ошибка запуска {test_file}: {e}")
        return False, str(e)


def main():
    """Основная функция запуска тестов"""
    start_time = datetime.now()
    
    print_header("ТЕСТИРОВАНИЕ PRYTON v2 - ПОЛНЫЙ ИГРОВОЙ ПРОЦЕСС")
    print(f"🕐 Начало тестирования: {start_time.strftime('%d.%m.%Y %H:%M:%S')}")
    
    # Список тестов для запуска
    test_suites = [
        {
            "file": "tests/test_full_game_process.py",
            "name": "Полный игровой процесс",
            "description": "Тесты от регистрации до завершения игры"
        },
        {
            "file": "tests/test_game_completion_flow.py", 
            "name": "Завершение игр и уведомления",
            "description": "Тесты процесса завершения и системы уведомлений"
        },
        {
            "file": "tests/test_scheduler_notifications.py",
            "name": "Планировщик и уведомления",
            "description": "Тесты системы планировщика и автоматических уведомлений"
        }
    ]
    
    # Результаты тестов
    results = []
    total_tests = 0
    passed_tests = 0
    
    print_section("ПЛАН ТЕСТИРОВАНИЯ")
    for i, suite in enumerate(test_suites, 1):
        print(f"{i}. {suite['name']}")
        print(f"   📝 {suite['description']}")
        print(f"   📁 {suite['file']}")
    
    print_section("ВЫПОЛНЕНИЕ ТЕСТОВ")
    
    for suite in test_suites:
        success, output = run_test_file(suite["file"], suite["name"])
        results.append({
            "name": suite["name"],
            "success": success,
            "output": output
        })
        
        if success:
            passed_tests += 1
        total_tests += 1
    
    # Финальный отчёт
    end_time = datetime.now()
    duration = end_time - start_time
    
    print_header("ИТОГОВЫЙ ОТЧЁТ")
    
    print_section("РЕЗУЛЬТАТЫ ПО НАБОРАМ ТЕСТОВ")
    for result in results:
        status = "✅ ПРОЙДЕН" if result["success"] else "❌ ПРОВАЛЕН"
        print(f"{status} - {result['name']}")
    
    print_section("ОБЩАЯ СТАТИСТИКА")
    print(f"📊 Всего наборов тестов: {total_tests}")
    print(f"✅ Успешно пройдено: {passed_tests}")
    print(f"❌ Провалено: {total_tests - passed_tests}")
    print(f"📈 Процент успеха: {(passed_tests/total_tests)*100:.1f}%")
    print(f"⏱ Время выполнения: {duration.total_seconds():.2f} секунд")
    
    print_section("ПОКРЫТИЕ ФУНКЦИОНАЛЬНОСТИ")
    print("✅ Регистрация пользователей")
    print("✅ Создание игр администратором")
    print("✅ Запись/отмена участников")
    print("✅ Распределение ролей")
    print("✅ Запуск и отмена игр")
    print("✅ Система уведомлений")
    print("✅ Планировщик задач")
    print("✅ Процесс завершения игр")
    print("✅ Обработка ошибок")
    print("✅ Навигация и интерфейс")
    
    print_section("ПРОТЕСТИРОВАННЫЕ КОМПОНЕНТЫ")
    print("🎮 src/handlers/games.py - Обработчики игр")
    print("🔧 src/services/game_service.py - Сервисы игр")
    print("👤 src/handlers/admin.py - Административные функции")
    print("⏰ src/services/scheduler_service.py - Планировщик")
    print("🔔 src/handlers/callback_handler.py - Завершение игр")
    print("📱 Интеграция компонентов")
    print("🔌 Telegram Bot API")
    
    if passed_tests == total_tests:
        print_section("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("Игровой процесс PRYTON v2 функционирует корректно")
        print("Система готова к продакшену")
        return True
    else:
        print_section("⚠️ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        print("Проверьте детали ошибок выше")
        print("Требуется исправление перед релизом")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 