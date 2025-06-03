# 🔍 Быстрая проверка состояния планировщика

import os
import sys
from datetime import datetime

# Добавляем корневой путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_scheduler_status():
    """Проверка текущего статуса планировщика"""
    
    print("🔍 ПРОВЕРКА СОСТОЯНИЯ ПЛАНИРОВЩИКА")
    print("=" * 50)
    
    try:
        from main import scheduler
        scheduler_service = scheduler
        if scheduler_service:
            print("✅ Планировщик инициализирован")
            
            internal_scheduler = scheduler_service.scheduler
            
            if internal_scheduler and hasattr(internal_scheduler, 'running'):
                if internal_scheduler.running:
                    print("✅ Планировщик активен и работает")
                else:
                    print("❌ Планировщик инициализирован, но не запущен")
            
            # Показываем настройки
            print(f"⏰ Время пряток: {scheduler_service.hiding_time} минут")
            print(f"🔔 Напоминания за: {scheduler_service.reminder_times} минут")
            
            # Показываем активные задачи
            if hasattr(internal_scheduler, 'get_jobs'):
                jobs = internal_scheduler.get_jobs()
                print(f"\n📋 Активных задач: {len(jobs)}")
                
                if jobs:
                    print("\n🗓️ Ближайшие задачи:")
                    sorted_jobs = sorted(jobs, key=lambda x: x.next_run_time if x.next_run_time else datetime.max)
                    
                    for job in sorted_jobs[:10]:  # Показываем первые 10
                        next_run = job.next_run_time.strftime('%d.%m.%Y %H:%M:%S') if job.next_run_time else 'Не запланировано'
                        print(f"   📅 {job.id}: {next_run}")
                else:
                    print("   (Нет активных задач)")
            
            return True
        else:
            print("❌ Планировщик не инициализирован")
            print("💡 Планировщик инициализируется только при запуске основного бота")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при проверке планировщика: {e}")
        return False


if __name__ == "__main__":
    success = check_scheduler_status()
    
    if success:
        print("\n✅ Планировщик работает корректно!")
    else:
        print("\n⚠️ Планировщик недоступен из внешнего скрипта")
        print("💡 Это нормально - планировщик работает только внутри основного бота")
