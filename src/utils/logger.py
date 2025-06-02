import os
import sys
from loguru import logger

def setup_logger():
    """Настройка логирования с помощью loguru"""
    
    # Создание директории для логов, если её нет
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Путь к файлу лога
    log_file = os.path.join(logs_dir, "bot.log")
    
    # Настройка формата
    format_string = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    
    # Удаление стандартного обработчика
    logger.remove()
    
    # Добавление обработчика для вывода в консоль
    logger.add(sys.stderr, format=format_string, level="INFO")
    
    # Добавление обработчика для записи в файл
    logger.add(
        log_file,
        format=format_string,
        level="DEBUG",
        rotation="1 day",  # Ротация каждый день
        retention="30 days",  # Хранение логов за 30 дней
        compression="zip",  # Сжатие старых логов
    )
    
    return logger 