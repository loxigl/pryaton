# Импорты клавиатур будут добавлены по мере разработки

from src.keyboards.reply import (
    get_phone_keyboard,
    get_district_keyboard,
    get_role_keyboard,
    get_confirmation_keyboard,
    get_main_keyboard,
    get_contextual_main_keyboard,
    get_game_location_keyboard,
    get_photo_action_keyboard,
    remove_keyboard
)

from src.keyboards.inline import (
    get_game_list_keyboard,
    get_game_actions_keyboard,
    get_admin_game_keyboard,
    get_admin_create_game_keyboard,
    get_location_keyboard,
    get_game_finish_keyboard
)

__all__ = [
    "get_phone_keyboard",
    "get_district_keyboard",
    "get_role_keyboard",
    "get_confirmation_keyboard",
    "get_main_keyboard",
    "get_contextual_main_keyboard",
    "get_game_location_keyboard",
    "get_photo_action_keyboard",
    "remove_keyboard",
    "get_game_list_keyboard",
    "get_game_actions_keyboard",
    "get_admin_game_keyboard",
    "get_admin_create_game_keyboard",
    "get_location_keyboard",
    "get_game_finish_keyboard"
] 