import asyncio
import logging
import os
import time
import signal
from dotenv import load_dotenv
from telegram.ext import Application, ConversationHandler, MessageHandler, filters
from sqlalchemy import text

from src.handlers.start import (
    start_handler, 
    process_name, 
    process_phone, 
    process_district, 
    process_role, 
    process_rules_confirmation,
    cancel,
    ENTER_NAME, 
    ENTER_PHONE, 
    ENTER_DISTRICT, 
    ENTER_ROLE, 
    CONFIRM_RULES,
    process_car_brand,
    process_car_color,
    process_car_number,
    ENTER_CAR_BRAND,
    ENTER_CAR_COLOR,
    ENTER_CAR_NUMBER
)
from src.handlers.games import game_handlers
from src.handlers.admin import (
    admin_handlers, 
    create_game_conversation,
    edit_rules_conversation,
    districts_conversation,
    roles_conversation,
    edit_game_fields_conversation
)
from src.handlers.zone_admin import zone_management_conversation
from src.handlers.scheduler_admin import register_scheduler_admin_handlers
from src.handlers.text_messages import text_message_handler
from src.handlers.callback_handler import callback_handler
from src.handlers.location import location_handlers
from src.handlers.photo import photo_handlers
from src.utils.logger import setup_logger
from src.models import create_tables
from src.models.base import engine
from src.services.enhanced_scheduler_service import init_enhanced_scheduler

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("Не найден токен Telegram бота. Укажите TELEGRAM_TOKEN в .env файле")

# Настройка логирования
logger = setup_logger()

# Глобальная переменная для отслеживания состояния завершения
should_exit = False
scheduler = None

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения программы"""
    global should_exit
    logger.info(f"Получен сигнал {sig}, завершение работы...")
    should_exit = True

def wait_for_db(max_attempts=30, delay=2):
    """Ожидание готовности базы данных перед запуском бота"""
    logger.info("Ожидание готовности базы данных...")
    
    for attempt in range(max_attempts):
        try:
            # Пробуем выполнить простой запрос к базе данных
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("База данных готова к работе")
            return True
        except Exception as e:
            logger.warning(f"Попытка {attempt+1}/{max_attempts}: БД недоступна, ожидание {delay} сек... ({str(e)})")
            time.sleep(delay)
    
    logger.error(f"База данных не стала доступна после {max_attempts} попыток")
    return False

async def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота PRYTON")
    
    # Ожидание готовности базы данных
    if not wait_for_db():
        logger.error("Не удалось подключиться к базе данных. Завершение работы.")
        return
    
    # Создание таблиц в БД, если их нет
    create_tables()
    logger.info("База данных инициализирована")
    
    # Создание экземпляра приложения
    application = Application.builder().token(TOKEN).build()
    
    # Инициализация улучшенного планировщика задач
    scheduler = init_enhanced_scheduler(application)
    
    # Создание обработчика диалога регистрации
    registration_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.ChatType.PRIVATE & (filters.Regex("^/start") | filters.Regex("^🏠 Главное меню")), start_handler)],
        states={
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)],
            ENTER_PHONE: [
                MessageHandler(filters.CONTACT, process_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_phone)
            ],
            ENTER_DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_district)],
            ENTER_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_role)],
            ENTER_CAR_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_car_brand)],
            ENTER_CAR_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_car_color)],
            ENTER_CAR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_car_number)],
            CONFIRM_RULES: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_rules_confirmation)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена"), cancel)]
    )
    
    # Регистрация обработчиков
    application.add_handler(registration_handler)
    
    # Регистрация обработчика создания игр (должен быть раньше admin_handlers)
    application.add_handler(create_game_conversation)
    
    # Регистрация обработчика редактирования правил
    application.add_handler(edit_rules_conversation)
    
    # Регистрация обработчиков управления настройками
    application.add_handler(districts_conversation)
    application.add_handler(roles_conversation)
    
    # Регистрация обработчика inline редактирования игр
    application.add_handler(edit_game_fields_conversation)
    
    # Регистрация обработчика управления зонами
    application.add_handler(zone_management_conversation)
    
    # Регистрация обработчиков игр
    for handler in game_handlers:
        application.add_handler(handler)
    
    # Регистрация обработчиков для админов
    for handler in admin_handlers:
        application.add_handler(handler)
    
    # Регистрация новых админских обработчиков планировщика
    register_scheduler_admin_handlers(application)
    
    # Регистрация обработчиков геолокации
    for handler in location_handlers:
        application.add_handler(handler)
    
    # Регистрация обработчиков фотографий
    for handler in photo_handlers:
        application.add_handler(handler)
    
    # Регистрация общего обработчика callback'ов
    application.add_handler(callback_handler)
    
    # Регистрация обработчика текстовых сообщений с клавиатуры
    # Он должен быть последним, чтобы не перехватывать команды
    application.add_handler(text_message_handler)
    
    # Запуск бота
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Запуск планировщика
    scheduler.start()
    
    logger.info("Бот успешно запущен")
    
    try:
        # Бесконечный цикл для поддержания работы бота
        while not should_exit:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал прерывания, завершение работы...")
    finally:
        # Корректное завершение работы бота
        logger.info("Остановка бота...")
        
        # Остановка планировщика
        scheduler.shutdown()
        
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    # Установка обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
    except Exception as e:
        logging.error(f"Ошибка: {e}", exc_info=True) 