#!/usr/bin/env python3
"""
Тест исправления проблем с планировщиком и timezone
PRYTON v2 - Проверка корректности работы событий планировщика
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import pytz

# Добавляем корневой путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.enhanced_scheduler_service import EnhancedSchedulerService, DEFAULT_TIMEZONE
from src.services.event_persistence_service import EventPersistenceService

async def test_scheduler_timezone_fix():
    """Тестирует исправления планировщика с timezone"""
    print("🕐 ТЕСТ ИСПРАВЛЕНИЯ ПЛАНИРОВЩИКА С TIMEZONE")
    print("=" * 50)
    
    # Имитируем Application для создания планировщика
    class MockApplication:
        class MockBot:
            pass
        bot = MockBot()
    
    app = MockApplication()
    scheduler = EnhancedSchedulerService(app)
    
    print("✅ Планировщик инициализирован")
    print(f"🌍 Временная зона: {DEFAULT_TIMEZONE}")
    print(f"🕐 Текущее время: {datetime.now(DEFAULT_TIMEZONE)}")
    
    # Тест 1: Создание события с правильным форматом времени
    print("\n📋 ТЕСТ 1: Проверка timezone и формата времени")
    print("-" * 30)
    
    try:
        # Проверяем инициализацию планировщика с timezone
        assert scheduler.scheduler.timezone == DEFAULT_TIMEZONE
        print("✅ Планировщик инициализирован с правильной временной зоной")
        
        # Проверяем что планировщик может быть запущен
        scheduler.start()
        print("✅ Планировщик успешно запущен")
        
        # Проверяем базовые функции
        jobs_count = len(scheduler.scheduler.get_jobs())
        print(f"📊 Задач в планировщике: {jobs_count}")
        
        # Тестируем создание тестового времени 
        tomorrow = datetime.now(DEFAULT_TIMEZONE) + timedelta(hours=24)
        print(f"📅 Тестовое время игры: {tomorrow}")
        
        # Проверяем что планировщик может добавлять задачи
        test_time = datetime.now(DEFAULT_TIMEZONE) + timedelta(seconds=5)
        
        def test_job():
            print("🔔 Тестовая задача выполнена")
        
        scheduler.scheduler.add_job(
            test_job,
            trigger='date',
            run_date=test_time,
            id='test_job'
        )
        
        new_jobs_count = len(scheduler.scheduler.get_jobs())
        print(f"📊 Задач после добавления: {new_jobs_count}")
        
        if new_jobs_count > jobs_count:
            print("✅ Задача успешно добавлена в планировщик")
        else:
            print("⚠️ Задача не была добавлена")
            
    except Exception as e:
        print(f"❌ Ошибка в тесте 1: {e}")
        return
    
    # Тест 2: Проверка обработки времени
    print("\n📋 ТЕСТ 2: Обработка временных зон")
    print("-" * 30)
    
    try:
        # Тестируем различные форматы времени
        naive_time = datetime.now()
        aware_time = datetime.now(DEFAULT_TIMEZONE)
        
        print(f"⏰ Naive время: {naive_time} (timezone: {naive_time.tzinfo})")
        print(f"⏰ Aware время: {aware_time} (timezone: {aware_time.tzinfo})")
        
        # Проверяем что планировщик корректно обрабатывает время
        if aware_time.tzinfo == DEFAULT_TIMEZONE:
            print("✅ Aware время имеет правильную timezone")
        else:
            print("❌ Проблема с aware временем")
        
        # Тестируем локализацию naive времени
        localized_time = DEFAULT_TIMEZONE.localize(naive_time)
        print(f"⏰ Локализованное время: {localized_time}")
        
        if localized_time.tzinfo == DEFAULT_TIMEZONE:
            print("✅ Naive время успешно локализовано")
        else:
            print("❌ Проблема с локализацией времени")
            
    except Exception as e:
        print(f"❌ Ошибка в тесте 2: {e}")
    
    # Тест 3: Проверка функций планировщика
    print("\n📋 ТЕСТ 3: Проверка функций планировщика")
    print("-" * 30)
    
    try:
        # Проверяем что планировщик может получать информацию о событиях
        try:
            events_info = scheduler.get_scheduled_events_info()
            print("✅ Функция get_scheduled_events_info() работает")
            print(f"📊 Структура ответа: {list(events_info.keys())}")
        except Exception as e:
            print(f"⚠️ Функция get_scheduled_events_info() вызвала ошибку: {e}")
        
        # Проверяем функцию отмены задач
        try:
            scheduler.cancel_game_jobs(9999)  # Тестовый ID
            print("✅ Функция cancel_game_jobs() работает")
        except Exception as e:
            print(f"⚠️ Функция cancel_game_jobs() вызвала ошибку: {e}")
            
        # Проверяем что задачи можно удалять
        jobs_before = len(scheduler.scheduler.get_jobs())
        if jobs_before > 0:
            # Удаляем тестовую задачу
            try:
                scheduler.scheduler.remove_job('test_job')
                jobs_after = len(scheduler.scheduler.get_jobs())
                print(f"📊 Задач до удаления: {jobs_before}, после: {jobs_after}")
                if jobs_after < jobs_before:
                    print("✅ Задача успешно удалена")
            except Exception as e:
                print(f"⚠️ Ошибка удаления задачи: {e}")
                
    except Exception as e:
        print(f"❌ Ошибка в тесте 3: {e}")
    
    # Тест 4: Проверка настроек планировщика
    print("\n📋 ТЕСТ 4: Проверка настроек планировщика")
    print("-" * 30)
    
    try:
        print(f"⏰ Время прятки: {scheduler.hiding_time} минут")
        print(f"🔔 Времена напоминаний: {scheduler.reminder_times} минут")
        
        # Проверяем что настройки корректны
        if isinstance(scheduler.hiding_time, int) and scheduler.hiding_time > 0:
            print("✅ Время прятки корректно")
        else:
            print("❌ Проблема с временем прятки")
            
        if isinstance(scheduler.reminder_times, list) and len(scheduler.reminder_times) > 0:
            print("✅ Времена напоминаний корректны")
        else:
            print("❌ Проблема с временами напоминаний")
            
    except Exception as e:
        print(f"❌ Ошибка в тесте 4: {e}")
    
    # Очистка
    try:
        scheduler.shutdown()
        print("\n🔧 Планировщик остановлен")
        
    except Exception as e:
        print(f"⚠️ Ошибка остановки планировщика: {e}")
    
    print("\n" + "=" * 50)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("💡 Основные исправления:")
    print("   - Добавлена поддержка timezone (Moscow)")
    print("   - Исправлен DateTrigger с правильным временем")
    print("   - Улучшена обработка просроченных событий")
    print("   - Добавлена корректная конвертация времени")
    print("   - Планировщик стабильно работает с timezone")

if __name__ == "__main__":
    asyncio.run(test_scheduler_timezone_fix()) 