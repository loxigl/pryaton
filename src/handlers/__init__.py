from src.handlers.start import (
    start_handler, 
    process_name, 
    process_phone, 
    process_district, 
    process_role, 
    process_rules_confirmation,
    cancel
)

from src.handlers.games import game_handlers
from src.handlers.admin import admin_handlers, create_game_conversation
from src.handlers.text_messages import text_message_handler, handle_text_message
from src.handlers.contextual_actions import (
    handle_my_game_button,
    handle_game_status_button,
    handle_send_location_button,
    handle_game_results_button
)

# Создаем обработчики
from telegram.ext import MessageHandler, filters

# Обработчик текстовых сообщений (должен быть последним)
text_message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)

__all__ = [
    "start_handler",
    "process_name",
    "process_phone",
    "process_district",
    "process_role",
    "process_rules_confirmation",
    "cancel",
    "game_handlers",
    "admin_handlers",
    "create_game_conversation",
    "text_message_handler",
    "handle_my_game_button",
    "handle_game_status_button",
    "handle_send_location_button",
    "handle_game_results_button"
] 