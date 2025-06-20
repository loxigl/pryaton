import asyncio
from functools import wraps
import logging
import os
import time
import signal
from dotenv import load_dotenv
from telegram.ext import Application, ConversationHandler, MessageHandler, filters
from sqlalchemy import text
import sentry_sdk

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
from src.services.metrics_service import metrics_service

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
SENTRY_DSN = os.getenv("SENTRY_DSN")

if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)

if not TOKEN:
    raise ValueError("Не найден токен Telegram бота. Укажите TELEGRAM_TOKEN в .env файле")

# Настройка логирования
logger = setup_logger()

def wrap_callback(fn, threshold: float):
    @wraps(fn)
    async def wrapper(update, context, *args, **kwargs):
        start = time.perf_counter()
        try:
            return await fn(update, context, *args, **kwargs)
        finally:
            duration = time.perf_counter() - start
            metrics_service.observe_latency(duration)
            name = getattr(fn, "__name__", repr(fn))
            user = update.effective_user.id if update.effective_user else "unknown"
            if duration > threshold:
                metrics_service.record_error()
                logger.warning(f"⚠️ SLOW: {name} took {duration:.2f}s (user={user})")
            else:
                logger.info(f"{name} took {duration:.2f}s")
    return wrapper

def wrap_handler(handler, threshold: float):
    handler.callback = wrap_callback(handler.callback, threshold)
    return handler

def wrap_all_handlers(application, threshold: float = 2.0):
    """
    Оборачиваем ВСЕ хендлеры, в том числе вложенные в ConversationHandler,
    но меняем приватные списки _entry_points и _fallbacks, чтобы не ломать property.
    """
    for group, handlers in application.handlers.items():
        for handler in handlers:
            if isinstance(handler, ConversationHandler):
                # оборачивам entry_points, fallbacks и states
                handler._entry_points = [
                    wrap_handler(h, threshold) for h in handler._entry_points
                ]
                # states — это обычный dict, можно менять через handler.states
                for state, hlist in handler.states.items():
                    handler.states[state] = [
                        wrap_handler(h, threshold) for h in hlist
                    ]
                handler._fallbacks = [
                    wrap_handler(h, threshold) for h in handler._fallbacks
                ]
            elif hasattr(handler, "callback"):
                wrap_handler(handler, threshold)
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

    # Запуск сервиса метрик
    metrics_service.start()
    
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
    
    wrap_all_handlers(application,threshold=4.0)

    from aiohttp import web

    # Парсим список админов из ENV
    ADMIN_USER_IDS = os.getenv("ADMIN_USER_IDS", "")
    ADMIN_IDS = [int(x) for x in ADMIN_USER_IDS.split(",") if x]

    async def alert_handler(request: web.Request) -> web.Response:
        """
        Ожидает JSON от Alertmanager (webhook_config),
        рассылает текст админам в Telegram.
        """
        data = await request.json()
        alerts = data.get("alerts", [])
        lines = []
        for a in alerts:
            status = a.get("status", "")
            name = a.get("labels", {}).get("alertname", "")
            desc = a.get("annotations", {}).get("description", "")
            # Вы можете брать summary / description по вкусу
            lines.append(f"*[{status}]* _{name}_\n{desc}")
        _text = "\n\n".join(lines) or "❗️ Пустой алерт"

        # Шлём по каждому администратору
        for uid in ADMIN_IDS:
            try:
                await application.bot.send_message(
                    chat_id=uid,
                    text=_text,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить алерт {uid}: {e}")

        return web.Response(text="ok")

    async def start_webhook(app: Application):
        """
        Запустим aiohttp на порту 8001
        """
        webapp = web.Application()
        webapp.add_routes([web.post("/alert", alert_handler)])
        runner = web.AppRunner(webapp)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("ALERT_WEBHOOK_PORT", "8001")))
        await site.start()
        logger.info("Alertmanager webhook listening on port %s", os.getenv("ALERT_WEBHOOK_PORT", "8001"))


    # Запуск бота
    await application.initialize()
    await start_webhook(application)
    await application.start()
    await application.updater.start_polling()
    
    # Запуск планировщика
    scheduler.start()
    metrics_service.update_scheduler_jobs(len(scheduler.scheduler.get_jobs()))
    
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
        metrics_service.update_scheduler_jobs(0)
        metrics_service.stop()
        
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
        metrics_service.record_error()

