from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from src.services.settings_service import SettingsService

def get_phone_keyboard():
    """Клавиатура для запроса номера телефона"""
    button = KeyboardButton(text="📱 Поделиться контактом", request_contact=True)
    skip_button = KeyboardButton(text="⏭ Пропустить")
    cancel_button = KeyboardButton(text="❌ Отмена")
    keyboard = ReplyKeyboardMarkup([[button], [skip_button], [cancel_button]], resize_keyboard=True)
    return keyboard

def get_district_keyboard():
    """Клавиатура для выбора района"""
    districts = SettingsService.get_districts()
    
    # Формирование кнопок по 2 в ряд
    buttons = []
    row = []
    for district in districts:
        if len(row) < 2:
            row.append(KeyboardButton(text=district))
        else:
            buttons.append(row)
            row = [KeyboardButton(text=district)]
    
    if row:  # Добавляем оставшиеся кнопки
        buttons.append(row)
    
    # Добавляем кнопку отмены
    buttons.append([KeyboardButton(text="❌ Отмена")])
    
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    return keyboard

def get_role_keyboard():
    """Клавиатура для выбора роли по умолчанию"""
    roles = SettingsService.get_available_roles()
    buttons = [[KeyboardButton(text=role)] for role in roles]
    
    # Добавляем кнопку отмены
    buttons.append([KeyboardButton(text="❌ Отмена")])
    
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    return keyboard

def get_confirmation_keyboard():
    """Клавиатура для подтверждения"""
    buttons = [
        [KeyboardButton(text="✅ Да, согласен с правилами")], 
        [KeyboardButton(text="❌ Нет, не согласен")]
    ]
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    return keyboard

def get_main_keyboard(is_admin=False):
    """Основная клавиатура после регистрации (legacy - для обратной совместимости)"""
    buttons = [
        [KeyboardButton(text="🎮 Доступные игры"), KeyboardButton(text="🎯 Мои игры")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="ℹ️ Помощь")]
    ]
    
    if is_admin:
        buttons.append([KeyboardButton(text="🔑 Админ-панель"), KeyboardButton(text="📊 Мониторинг")])
        buttons.append([KeyboardButton(text="📅 События планировщика")])
    
    # Добавляем кнопку обновления главного меню
    buttons.append([KeyboardButton(text="🏠 Главное меню")])
    
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    return keyboard

def get_contextual_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Получить контекстную главную клавиатуру в зависимости от статуса пользователя"""
    try:
        from src.services.dynamic_keyboard_service import DynamicKeyboardService
        return DynamicKeyboardService.get_contextual_main_keyboard(user_id)
    except Exception:
        # Fallback на обычную клавиатуру при ошибке импорта или других проблемах
        from src.services.user_service import UserService
        return get_main_keyboard(UserService.is_admin(user_id))

def get_game_location_keyboard():
    """Клавиатура для отправки геолокации в игре"""
    button = KeyboardButton(text="📍 Отправить мое местоположение", request_location=True)
    cancel_button = KeyboardButton(text="❌ Отменить")
    menu_button = KeyboardButton(text="🏠 Главное меню")
    
    keyboard = ReplyKeyboardMarkup([
        [button], 
        [cancel_button, menu_button]
    ], resize_keyboard=True)
    return keyboard

def get_photo_action_keyboard():
    """Клавиатура для действий с фотографией в игре"""
    buttons = [
        [KeyboardButton(text="📸 Сделать фото"), KeyboardButton(text="🖼 Выбрать из галереи")],
        [KeyboardButton(text="❌ Отменить"), KeyboardButton(text="🏠 Главное меню")]
    ]
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    return keyboard

def get_back_keyboard():
    """Клавиатура с кнопкой назад"""
    buttons = [
        [KeyboardButton(text="🏠 Главное меню")]
    ]
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    return keyboard

def remove_keyboard():
    """Удаление клавиатуры"""
    return ReplyKeyboardRemove() 