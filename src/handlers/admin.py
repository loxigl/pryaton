from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler, 
    CallbackContext, 
    ConversationHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters
)
from datetime import datetime, timedelta
import re
from loguru import logger
import os
import pytz
import asyncio

from src.services.enhanced_scheduler_service import format_msk_time,format_msk_datetime
from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.settings_service import SettingsService
from src.models.game import GameStatus, GameRole, GameParticipant
from src.models.base import get_db
from src.keyboards.inline import get_admin_game_keyboard
from src.keyboards.reply import get_district_keyboard, get_contextual_main_keyboard

# Новые импорты для работы с зонами
from src.services.location_service import LocationService
from src.services.zone_management_service import ZoneManagementService
# Новые импорты для настроек и ручного управления
from src.services.game_settings_service import GameSettingsService
from src.services.manual_game_control_service import ManualGameControlService
from src.keyboards.inline import (
    get_game_settings_keyboard, 
    get_automation_settings_keyboard,
    get_time_settings_keyboard,
    get_manual_control_keyboard,
    get_participants_management_keyboard,
    get_participant_actions_keyboard,
    get_role_assignment_type_keyboard
)

# Состояния для создания игры
CREATE_DISTRICT, CREATE_DATE, CREATE_TIME, CREATE_MAX_PARTICIPANTS, CREATE_MAX_DRIVERS, CREATE_DESCRIPTION, CREATE_ZONE, CREATE_CONFIRM = range(8)

# Состояния для создания зон в процессе создания игры
CREATE_ZONE_NAME, CREATE_ZONE_COORDINATES, CREATE_ZONE_RADIUS, CREATE_ZONE_CONFIRM = range(25, 29)

# Состояния для редактирования правил
EDIT_RULES = 10

# Состояния для редактирования районов
DISTRICT_ACTION, ADD_DISTRICT_NAME, REMOVE_DISTRICT_NAME = range(11, 14)

# Состояния для редактирования ролей
ROLE_ACTION = 5
EDIT_ROLE_DISPLAY = 6
ENTER_NEW_ROLE_DISPLAY = 7

# Состояния для редактирования игр
EDIT_GAME_FIELD, EDIT_GAME_VALUE, EDIT_GAME_SAVE = range(17, 20)

# Состояния для inline редактирования
EDIT_GAME_DISTRICT_VALUE, EDIT_GAME_DATETIME_VALUE, EDIT_GAME_PARTICIPANTS_VALUE, EDIT_GAME_DRIVERS_VALUE, EDIT_GAME_DESCRIPTION_VALUE = range(20, 25)

# Шаблоны для колбэков
ADMIN_GAME_PATTERN = r"admin_game_(\d+)"
ADMIN_CANCEL_PATTERN = r"cancel_game_(\d+)"
ADMIN_START_PATTERN = r"start_game_(\d+)"
ADMIN_EDIT_GAME_PATTERN = r"edit_game_(\d+)"
EDIT_DISTRICT_PATTERN = r"edit_district_(\d+)"
EDIT_DATETIME_PATTERN = r"edit_datetime_(\d+)"
EDIT_PARTICIPANTS_PATTERN = r"edit_participants_(\d+)"
EDIT_DRIVERS_PATTERN = r"edit_drivers_(\d+)"
EDIT_DESCRIPTION_PATTERN = r"edit_description_(\d+)"
SET_DISTRICT_PATTERN = r"set_district_(\d+)_(.+)"
SET_PARTICIPANTS_PATTERN = r"set_participants_(\d+)_(\d+)"
SET_DRIVERS_PATTERN = r"set_drivers_(\d+)_(\d+)"

# Определяем временную зону (по умолчанию московское время)
DEFAULT_TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "Europe/Moscow"))

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Получение админской клавиатуры"""
    return ReplyKeyboardMarkup([
        ["🎮 Создать игру", "📋 Список игр"],
        ["👥 Управление пользователями", "📊 Мониторинг"],
        ["📅 События планировщика", "🏙️ Управление районами"],
        ["🗺 Управление зонами", "👤 Управление ролями"],
        ["📋 Редактировать правила", "⚙️ Настройки игры"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)

def get_admin_or_main_keyboard(user_id: int, admin_context: bool = False) -> ReplyKeyboardMarkup:
    """
    Получение правильной клавиатуры в зависимости от контекста
    
    Args:
        user_id: ID пользователя
        admin_context: True если пользователь находится в админ-контексте
    """
    is_admin = UserService.is_admin(user_id)
    
    if is_admin and admin_context:
        return get_admin_keyboard()
    else:
        return get_contextual_main_keyboard(user_id)

async def admin_command(update: Update, context: CallbackContext) -> int:
    """Обработчик команды /admin - открывает админ-панель"""
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await update.message.reply_text(
            "У вас нет прав доступа к этой команде.",
            reply_markup=get_admin_or_main_keyboard(user_id, True)
        )
        return ConversationHandler.END
    
    admin_keyboard = get_admin_or_main_keyboard(user_id, True)
    
    await update.message.reply_text(
        "🔑 <b>Админ-панель</b>\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=admin_keyboard,
        parse_mode="HTML"
    )
    return ConversationHandler.END

async def admin_games_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /admingames - показывает список всех игр для админа"""
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await update.message.reply_text(
            "У вас нет прав доступа к этой команде.",
            reply_markup=get_admin_or_main_keyboard(user_id, True)
        )
        return
    
    # Получаем список всех игр (можно добавить пагинацию)
    all_games = GameService.get_active_games(limit=10)
    
    if not all_games:
        await update.message.reply_text(
            "Сейчас нет запланированных игр.",
            reply_markup=get_admin_or_main_keyboard(user_id, True)
        )
        return
    
    # Создаем клавиатуру для админа
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{game.district} - {format_msk_datetime(game.scheduled_at)} ({len(game.participants)}/{game.max_participants})",
            callback_data=f"admin_game_{game.id}"
        )] for game in all_games
    ] + [[InlineKeyboardButton("+ Создать новую игру", callback_data="create_game")]])
    
    await update.message.reply_text(
        "📋 <b>Список всех игр (админ)</b>\n\n"
        "Выберите игру для управления:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def admin_game_button(update: Update, context: CallbackContext) -> None:
    """Обработчик нажатия на кнопку с игрой в админке"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Извлекаем ID игры из колбэка
    match = re.match(ADMIN_GAME_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    game = GameService.get_game_by_id(game_id)
    
    if not game:
        await query.edit_message_text("Игра не найдена или была удалена.")
        return
    
    # Готовим информацию об игре для админа
    participants_info = "\n".join([
        f"- {p.user.name} ({p.role.value if p.role else 'не назначена'})" 
        for p in game.participants
    ]) if game.participants else "Нет участников"
    
    game_info = (
        f"🎮 <b>Управление игрой #{game.id}</b>\n\n"
        f"📍 <b>Район:</b> {game.district}\n"
        f"⏰ <b>Дата и время:</b> {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"👥 <b>Участники:</b> {len(game.participants)}/{game.max_participants}\n"
        f"🚦 <b>Статус:</b> {game.status.value}\n"
    )
    
    if game.description:
        game_info += f"\n📝 <b>Описание:</b>\n{game.description}\n"
    
    game_info += f"\n<b>Список участников:</b>\n{participants_info}"
    
    # Создаем клавиатуру с админскими действиями
    keyboard = get_admin_game_keyboard(game)
    
    await query.edit_message_text(
        game_info,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def cancel_game_button(update: Update, context: CallbackContext) -> None:
    """Обработчик отмены игры администратором"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Извлекаем ID игры из колбэка
    match = re.match(ADMIN_CANCEL_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Отменяем игру
    success = GameService.cancel_game(game_id, "Игра отменена администратором")
    
    if not success:
        await query.edit_message_text(
            "❌ Не удалось отменить игру.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_admin_games")
            ]])
        )
        return
    
    await query.edit_message_text(
        "✅ <b>Игра успешно отменена.</b>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_admin_games")
        ]]),
        parse_mode="HTML"
    )

async def start_game_button(update: Update, context: CallbackContext) -> None:
    """Обработчик запуска игры администратором"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Извлекаем ID игры из колбэка
    match = re.match(ADMIN_START_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Запускаем игру
    success = GameService.start_game(game_id, "manual")
    
    if not success:
        await query.edit_message_text(
            "❌ Не удалось запустить игру. Возможно, не все роли назначены.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")
            ]])
        )
        return
    
    await query.edit_message_text(
        "✅ <b>Игра успешно запущена!</b>\n\n"
        "Всем участникам отправлены уведомления о начале игры.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_admin_games")
        ]]),
        parse_mode="HTML"
    )

async def start_game_early_button(update: Update, context: CallbackContext) -> None:
    """Обработчик досрочного запуска игры администратором"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Извлекаем ID игры из колбэка
    match = re.match(r"start_early_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Запускаем игру досрочно
    success = GameService.start_game(game_id, "early")
    
    if not success:
        await query.edit_message_text(
            "❌ Не удалось запустить игру досрочно. Возможно, не все роли назначены или недостаточно участников.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")
            ]])
        )
        return
    
    await query.edit_message_text(
        "⚡ <b>Игра запущена досрочно!</b>\n\n"
        "Всем участникам отправлены уведомления о досрочном начале игры.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_admin_games")
        ]]),
        parse_mode="HTML"
    )

async def edit_game_inline_button(update: Update, context: CallbackContext) -> None:
    """Обработчик inline кнопки редактирования игры"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Извлекаем ID игры из колбэка
    match = re.match(ADMIN_EDIT_GAME_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    game = GameService.get_game_by_id(game_id)
    
    if not game or not GameService.can_edit_game(game_id):
        await query.edit_message_text(
            "❌ Игра не найдена или не может быть отредактирована.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")
            ]])
        )
        return
    
    # Показываем текущие данные игры и кнопки для редактирования
    max_seekers = game.max_participants - game.max_drivers
    game_info = (
        f"✏️ <b>Редактирование игры #{game.id}</b>\n\n"
        f"📍 <b>Район:</b> {game.district}\n"
        f"⏰ <b>Дата и время:</b> {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"👥 <b>Участников:</b> {game.max_participants}\n"
        f"🚗 <b>Водителей:</b> {game.max_drivers}\n"
        f"🔍 <b>Искателей:</b> {max_seekers}\n"
        f"📝 <b>Описание:</b> {game.description or 'Не указано'}\n\n"
        f"Выберите что хотите изменить:"
    )
    
    # Создаем inline клавиатуру для редактирования
    edit_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Изменить район", callback_data=f"edit_district_{game_id}")],
        [InlineKeyboardButton("⏰ Изменить дату/время", callback_data=f"edit_datetime_{game_id}")],
        [InlineKeyboardButton("👥 Изменить кол-во участников", callback_data=f"edit_participants_{game_id}")],
        [InlineKeyboardButton("🚗 Изменить кол-во водителей", callback_data=f"edit_drivers_{game_id}")],
        [InlineKeyboardButton("📝 Изменить описание", callback_data=f"edit_description_{game_id}")],
        [InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")]
    ])
    
    await query.edit_message_text(
        game_info,
        reply_markup=edit_keyboard,
        parse_mode="HTML"
    )

async def edit_district_button(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки изменения района"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(EDIT_DISTRICT_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    game = GameService.get_game_by_id(game_id)
    
    if not game or not GameService.can_edit_game(game_id):
        await query.edit_message_text(
            "❌ Игра не найдена или не может быть отредактирована.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")
            ]])
        )
        return
    
    # Получаем список районов для выбора
    districts = SettingsService.get_districts()
    if not districts:
        await query.edit_message_text(
            "❌ Нет доступных районов.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")
            ]])
        )
        return
    
    # Создаем inline клавиатуру с районами
    district_buttons = []
    for district in districts:
        district_buttons.append([InlineKeyboardButton(
            f"{'✅ ' if district == game.district else ''}{district}", 
            callback_data=f"set_district_{game_id}_{district}"
        )])
    
    district_buttons.append([InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")])
    
    await query.edit_message_text(
        f"📍 <b>Изменение района для игры #{game_id}</b>\n\n"
        f"Текущий район: <b>{game.district}</b>\n\n"
        f"Выберите новый район:",
        reply_markup=InlineKeyboardMarkup(district_buttons),
        parse_mode="HTML"
    )

async def edit_datetime_button(update: Update, context: CallbackContext) -> int:
    """Обработчик кнопки редактирования даты и времени"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return ConversationHandler.END
    
    match = re.match(EDIT_DATETIME_PATTERN, query.data)
    if not match:
        return ConversationHandler.END
    
    game_id = int(match.group(1))
    game = GameService.get_game_by_id(game_id)
    
    if not game:
        await query.edit_message_text("Игра не найдена.")
        return ConversationHandler.END
    
    # Сохраняем ID игры в контексте
    context.user_data["edit_game_id"] = game_id
    
    await query.edit_message_text(
        f"📅 <b>Редактирование даты и времени</b>\n\n"
        f"Текущие дата и время: <b>{format_msk_datetime(game.scheduled_at)}</b>\n\n"
        f"Отправьте новые дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
        f"Например: 25.12.2024 18:30\n\n"
        f"Или отправьте /cancel для отмены.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")
        ]]),
        parse_mode="HTML"
    )
    
    return EDIT_GAME_DATETIME_VALUE


async def edit_participants_button(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки изменения количества участников"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(EDIT_PARTICIPANTS_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    game = GameService.get_game_by_id(game_id)
    
    if not game or not GameService.can_edit_game(game_id):
        await query.edit_message_text(
            "❌ Игра не найдена или не может быть отредактирована.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")
            ]])
        )
        return
    
    current_participants = len(game.participants)
    min_participants = max(current_participants, 3)
    
    # Создаем кнопки с разными количествами участников
    participant_buttons = []
    for i in range(min_participants, 21):  # От минимума до 20
        participant_buttons.append([InlineKeyboardButton(
            f"{'✅ ' if i == game.max_participants else ''}{i} участников", 
            callback_data=f"set_participants_{game_id}_{i}"
        )])
    
    participant_buttons.append([InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")])
    
    await query.edit_message_text(
        f"👥 <b>Изменение количества участников для игры #{game_id}</b>\n\n"
        f"Текущее количество: <b>{game.max_participants}</b>\n"
        f"Уже записано: <b>{current_participants}</b>\n\n"
        f"Выберите новое количество участников:",
        reply_markup=InlineKeyboardMarkup(participant_buttons),
        parse_mode="HTML"
    )

async def edit_drivers_button(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки изменения количества водителей"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(EDIT_DRIVERS_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    game = GameService.get_game_by_id(game_id)
    
    if not game or not GameService.can_edit_game(game_id):
        await query.edit_message_text(
            "❌ Игра не найдена или не может быть отредактирована.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")
            ]])
        )
        return
    
    # Создаем кнопки с разными количествами водителей
    driver_buttons = []
    max_drivers = game.max_participants - 1
    for i in range(1, max_drivers + 1):
        seekers = game.max_participants - i
        driver_buttons.append([InlineKeyboardButton(
            f"{'✅ ' if i == game.max_drivers else ''}{i} водителей, {seekers} искателей", 
            callback_data=f"set_drivers_{game_id}_{i}"
        )])
    
    driver_buttons.append([InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")])
    
    await query.edit_message_text(
        f"🚗 <b>Изменение количества водителей для игры #{game_id}</b>\n\n"
        f"Общее количество участников: <b>{game.max_participants}</b>\n"
        f"Текущее распределение: <b>{game.max_drivers} водителей, {game.max_participants - game.max_drivers} искателей</b>\n\n"
        f"Выберите новое распределение:",
        reply_markup=InlineKeyboardMarkup(driver_buttons),
        parse_mode="HTML"
    )

async def edit_description_button(update: Update, context: CallbackContext) -> int:
    """Обработчик кнопки изменения описания"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(EDIT_DESCRIPTION_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    game = GameService.get_game_by_id(game_id)
    
    if not game or not GameService.can_edit_game(game_id):
        await query.edit_message_text(
            "❌ Игра не найдена или не может быть отредактирована.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")
            ]])
        )
        return
    
    # Сохраняем ID игры в контексте для последующего использования
    context.user_data["edit_game_id"] = game_id
    
    current_description = game.description or "Нет описания"
    
    await query.edit_message_text(
        f"📝 <b>Изменение описания для игры #{game_id}</b>\n\n"
        f"Текущее описание:\n<i>{current_description}</i>\n\n"
        f"Напишите новое описание игры или отправьте <code>-</code> для удаления описания:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")
        ]]),
        parse_mode="HTML"
    )
    
    return EDIT_GAME_DESCRIPTION_VALUE

async def back_to_admin_games_button(update: Update, context: CallbackContext) -> None:
    """Обработчик возврата к списку игр в админке"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Получаем список всех игр
    all_games = GameService.get_active_games(limit=10)
    
    if not all_games:
        await query.edit_message_text(
            "Сейчас нет запланированных игр.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("+ Создать новую игру", callback_data="create_game")
            ]])
        )
        return
    
    # Создаем клавиатуру для админа
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{game.district} - {game.scheduled_at.strftime('%d.%m %H:%M')} ({len(game.participants)}/{game.max_participants})",
            callback_data=f"admin_game_{game.id}"
        )] for game in all_games
    ] + [[InlineKeyboardButton("+ Создать новую игру", callback_data="create_game")]])
    
    await query.edit_message_text(
        "📋 <b>Список всех игр (админ)</b>\n\n"
        "Выберите игру для управления:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def create_game_button(update: Update, context: CallbackContext) -> None:
    """Обработчик нажатия на кнопку создания игры"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    await query.edit_message_text(
        "🆕 <b>Создание новой игры</b>\n\n"
        "Пожалуйста, вернитесь в админ-панель и нажмите на кнопку '🎮 Создать игру' "
        "для начала процесса создания новой игры.",
        parse_mode="HTML"
    )

async def create_game_command(update: Update, context: CallbackContext) -> int:
    """Начало диалога создания игры"""
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await update.message.reply_text(
            "У вас нет прав доступа к этой команде.",
            reply_markup=get_admin_or_main_keyboard(user_id, True)
        )
        return ConversationHandler.END
    
    # Получаем клавиатуру с районами
    district_keyboard = get_district_keyboard()
    
    await update.message.reply_text(
        "🆕 <b>Создание новой игры</b>\n\n"
        "Шаг 1/8: Выберите район проведения игры:",
        reply_markup=district_keyboard,
        parse_mode="HTML"
    )
    
    return CREATE_DISTRICT

async def process_district(update: Update, context: CallbackContext) -> int:
    """Обработка выбора района"""
    district = update.message.text
    context.user_data["game_district"] = district
    
    await update.message.reply_text(
        f"Выбран район: {district}\n\n"
        "Шаг 2/8: Введите дату проведения игры в формате ДД.ММ.ГГГГ (например, 15.06.2025):",
        
        reply_markup=ReplyKeyboardRemove()
    )
    
    return CREATE_DATE

async def process_date(update: Update, context: CallbackContext) -> int:
    """Обработка ввода даты"""
    date_text = update.message.text
    
    # Проверка формата даты
    try:
        game_date = datetime.strptime(date_text, "%d.%m.%Y")
        context.user_data["game_date"] = game_date
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например, 15.06.2025):"
        )
        return CREATE_DATE
    
    await update.message.reply_text(
        f"Дата: {date_text}\n\n"
        "Шаг 3/8: Введите время проведения игры в формате ЧЧ:ММ (например, 18:30):"
    )
    
    return CREATE_TIME

async def process_time(update: Update, context: CallbackContext) -> int:
    """Обработка ввода времени"""
    time_text = update.message.text
    
    # Проверка формата времени
    try:
        hour, minute = map(int, time_text.split(":"))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Invalid time")
        
        game_date = context.user_data["game_date"]
        game_datetime = game_date.replace(hour=hour, minute=minute)
        context.user_data["game_datetime"] = game_datetime
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Неверный формат времени. Пожалуйста, введите время в формате ЧЧ:ММ (например, 18:30):"
        )
        return CREATE_TIME
    
    await update.message.reply_text(
        f"Время: {time_text}\n\n"
        "Шаг 4/8: Введите максимальное количество участников (от 3 до 20):"
    )
    
    return CREATE_MAX_PARTICIPANTS

async def process_max_participants(update: Update, context: CallbackContext) -> int:
    """Обработка ввода максимального количества участников"""
    try:
        max_participants = int(update.message.text)
        if max_participants < 3 or max_participants > 20:
            raise ValueError("Invalid number")
        
        context.user_data["max_participants"] = max_participants
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите число от 3 до 20:"
        )
        return CREATE_MAX_PARTICIPANTS
    
    await update.message.reply_text(
        f"Максимальное количество участников: {max_participants}\n\n"
        f"Шаг 5/8: Введите количество водителей (прячущихся) от 1 до {max_participants - 1}:"
    )
    
    return CREATE_MAX_DRIVERS

async def process_max_drivers(update: Update, context: CallbackContext) -> int:
    """Обработка ввода количества водителей"""
    max_participants = context.user_data["max_participants"]
    
    try:
        max_drivers = int(update.message.text)
        if max_drivers < 1 or max_drivers >= max_participants:
            raise ValueError("Invalid number")
        
        context.user_data["max_drivers"] = max_drivers
    except ValueError:
        await update.message.reply_text(
            f"❌ Пожалуйста, введите число от 1 до {max_participants - 1}:"
        )
        return CREATE_MAX_DRIVERS
    
    max_seekers = max_participants - max_drivers
    await update.message.reply_text(
        f"Количество водителей: {max_drivers}\n"
        f"Количество искателей: {max_seekers}\n\n"
        f"Шаг 6/8: Введите описание игры (или отправьте '-' для пропуска):"
    )
    
    return CREATE_DESCRIPTION

async def process_description(update: Update, context: CallbackContext) -> int:
    """Обработка ввода описания"""
    description = update.message.text
    
    if description == "-":
        description = None
    
    context.user_data["description"] = description
    
    # Теперь переходим к выбору зоны
    district = context.user_data["game_district"]
    
    # Получаем существующие зоны района
    district_zones = LocationService.get_district_zones(district)
    
    if district_zones:
        zone_text = (
            f"🗺️ <b>Шаг 7/8: Выбор игровой зоны</b>\n\n"
            f"📍 <b>Район:</b> {district}\n\n"
            f"<b>Доступные зоны района:</b>\n"
        )
        
        keyboard_buttons = []
        
        for zone in district_zones:
            zone_status = "🌟 " if zone.is_default else ""
            zone_active = "✅ " if zone.is_active else "❌ "
            zone_text += f"• {zone_active}{zone_status}<b>{zone.zone_name}</b>\n"
            zone_text += f"  📍 Центр: {zone.center_lat:.4f}, {zone.center_lon:.4f}\n"
            zone_text += f"  📏 Радиус: {zone.radius}м | 📐 Площадь: {zone.area_km2} км²\n"
            if zone.description:
                zone_text += f"  💬 {zone.description}\n"
            zone_text += "\n"
            
            if zone.is_active:
                keyboard_buttons.append([f"🎯 {zone.zone_name}"])
        
        zone_text += (
            f"<b>Варианты:</b>\n"
            f"• Выберите существующую зону из списка\n"
            f"• Нажмите '🆕 Создать новую зону' для игры\n"
            f"• Нажмите '⚙️ Без зоны' (использовать зону по умолчанию)\n\n"
            f"<i>🌟 - зона по умолчанию, ✅ - активная, ❌ - неактивная</i>"
        )
        
        keyboard_buttons.extend([
            ["🆕 Создать новую зону"],
            ["⚙️ Без зоны (автоматически)"],
            ["❌ Отменить создание игры"]
        ])
        
    else:
        zone_text = (
            f"🗺️ <b>Шаг 7/8: Выбор игровой зоны</b>\n\n"
            f"📍 <b>Район:</b> {district}\n\n"
            f"❌ <b>В этом районе пока нет созданных зон</b>\n\n"
            f"<b>Варианты:</b>\n"
            f"• 🆕 Создать новую зону для игры\n"
            f"• ⚙️ Продолжить без зоны (будет создана автоматически)\n"
        )
        
        keyboard_buttons = [
            ["🆕 Создать новую зону"],
            ["⚙️ Без зоны (автоматически)"],
            ["❌ Отменить создание игры"]
        ]
    
    keyboard = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True)
    
    await update.message.reply_text(
        zone_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return CREATE_ZONE

async def process_zone_selection(update: Update, context: CallbackContext) -> int:
    """Обработка выбора зоны"""
    zone_choice = update.message.text
    district = context.user_data["game_district"]
    
    if zone_choice == "❌ Отменить создание игры":
        await update.message.reply_text(
            "❌ Создание игры отменено.",
            reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    elif zone_choice == "⚙️ Без зоны (автоматически)":
        # Игра будет использовать зону по умолчанию автоматически
        context.user_data["game_zone"] = "auto"
        zone_info_text = "Игра будет использовать зону района по умолчанию (автоматически)"
        
    elif zone_choice == "🆕 Создать новую зону":
        # Переходим к созданию новой зоны
        await update.message.reply_text(
            f"🆕 <b>Создание новой зоны для игры</b>\n\n"
            f"📍 <b>Район:</b> {district}\n\n"
            f"Введите название зоны (например: 'Центр парка', 'Торговый центр'):",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        return CREATE_ZONE_NAME
        
    elif zone_choice.startswith("🎯 "):
        # Выбрана существующая зона
        zone_name = zone_choice.replace("🎯 ", "")
        district_zones = LocationService.get_district_zones(district)
        selected_zone = next((z for z in district_zones if z.zone_name == zone_name), None)
        
        if selected_zone:
            context.user_data["game_zone"] = selected_zone.id
            zone_info_text = (
                f"Выбрана зона: <b>{selected_zone.zone_name}</b>\n"
                f"📍 Центр: {selected_zone.center_lat:.4f}, {selected_zone.center_lon:.4f}\n"
                f"📏 Радиус: {selected_zone.radius}м"
            )
        else:
            await update.message.reply_text(
                "❌ Выбранная зона не найдена. Попробуйте еще раз.",
                reply_markup=get_district_keyboard()
            )
            return CREATE_ZONE
    else:
        await update.message.reply_text(
            "❌ Неизвестный выбор. Пожалуйста, используйте кнопки.",
            reply_markup=get_district_keyboard()
        )
        return CREATE_ZONE
    
    # Переходим к подтверждению
    return await show_final_confirmation(update, context, zone_info_text)

async def process_zone_name(update: Update, context: CallbackContext) -> int:
    """Обработка ввода названия новой зоны"""
    zone_name = update.message.text.strip()
    
    if len(zone_name) < 3:
        await update.message.reply_text(
            "❌ Название зоны должно содержать минимум 3 символа. Попробуйте еще раз:"
        )
        return CREATE_ZONE_NAME
    
    context.user_data["new_zone_name"] = zone_name
    
    await update.message.reply_text(
        f"Название зоны: <b>{zone_name}</b>\n\n"
        f"Введите координаты центра зоны в формате: <code>широта,долгота</code>\n"
        f"Например: <code>55.7558,37.6176</code>\n\n"
        f"💡 Можно получить координаты из карт Google/Yandex",
        parse_mode="HTML"
    )
    
    return CREATE_ZONE_COORDINATES

async def process_zone_coordinates(update: Update, context: CallbackContext) -> int:
    """Обработка ввода координат зоны"""
    coordinates_text = update.message.text.strip()
    
    try:
        lat_str, lon_str = coordinates_text.split(",")
        latitude = float(lat_str.strip())
        longitude = float(lon_str.strip())
        
        # Валидация координат
        if not (-90 <= latitude <= 90):
            raise ValueError("Широта должна быть в диапазоне от -90 до 90")
        if not (-180 <= longitude <= 180):
            raise ValueError("Долгота должна быть в диапазоне от -180 до 180")
            
        context.user_data["new_zone_lat"] = latitude
        context.user_data["new_zone_lon"] = longitude
        
    except (ValueError, IndexError) as e:
        await update.message.reply_text(
            f"❌ Неверный формат координат: {str(e)}\n\n"
            f"Введите координаты в формате: <code>широта,долгота</code>\n"
            f"Например: <code>55.7558,37.6176</code>",
            parse_mode="HTML"
        )
        return CREATE_ZONE_COORDINATES
    
    await update.message.reply_text(
        f"Координаты: <b>{latitude:.6f}, {longitude:.6f}</b>\n\n"
        f"Введите радиус зоны в метрах (от 100 до 5000):\n"
        f"💡 Рекомендуется: 500-1500м для городских районов",
        parse_mode="HTML"
    )
    
    return CREATE_ZONE_RADIUS

async def process_zone_radius(update: Update, context: CallbackContext) -> int:
    """Обработка ввода радиуса зоны"""
    try:
        radius = int(update.message.text.strip())
        
        if radius < 100 or radius > 5000:
            raise ValueError("Радиус должен быть от 100 до 5000 метров")
            
        context.user_data["new_zone_radius"] = radius
        
        # Показываем предпросмотр новой зоны
        zone_name = context.user_data["new_zone_name"]
        latitude = context.user_data["new_zone_lat"]
        longitude = context.user_data["new_zone_lon"]
        area_km2 = round((3.14159 * (radius / 1000) ** 2), 2)
        
        preview_text = (
            f"🗺️ <b>Предпросмотр новой зоны</b>\n\n"
            f"📍 <b>Название:</b> {zone_name}\n"
            f"🎯 <b>Центр:</b> {latitude:.6f}, {longitude:.6f}\n"
            f"📏 <b>Радиус:</b> {radius}м\n"
            f"📐 <b>Площадь:</b> {area_km2} км²\n\n"
            f"Всё верно?"
        )
        
        keyboard = ReplyKeyboardMarkup([
            ["✅ Да, создать зону"],
            ["❌ Нет, изменить"],
            ["⚙️ Отменить зону (без зоны)"]
        ], resize_keyboard=True)
        
        await update.message.reply_text(
            preview_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        return CREATE_ZONE_CONFIRM
        
    except ValueError as e:
        await update.message.reply_text(
            f"❌ {str(e)}\n\nВведите радиус зоны в метрах (от 100 до 5000):"
        )
        return CREATE_ZONE_RADIUS

async def process_zone_confirmation(update: Update, context: CallbackContext) -> int:
    """Обработка подтверждения создания зоны"""
    confirmation = update.message.text
    
    if confirmation == "✅ Да, создать зону":
        # Создаем новую зону
        district = context.user_data["game_district"]
        zone_name = context.user_data["new_zone_name"]
        latitude = context.user_data["new_zone_lat"]
        longitude = context.user_data["new_zone_lon"]
        radius = context.user_data["new_zone_radius"]
        
        try:
            new_zone = ZoneManagementService.create_district_zone(
                district_name=district,
                zone_name=zone_name,
                center_lat=latitude,
                center_lon=longitude,
                radius=radius,
                description=f"Зона создана для игры",
                is_default=False
            )
            
            if new_zone:
                context.user_data["game_zone"] = new_zone.id
                zone_info_text = (
                    f"Создана новая зона: <b>{zone_name}</b>\n"
                    f"📍 Центр: {latitude:.4f}, {longitude:.4f}\n"
                    f"📏 Радиус: {radius}м"
                )
                
                # Очищаем временные данные зоны
                for key in ["new_zone_name", "new_zone_lat", "new_zone_lon", "new_zone_radius"]:
                    context.user_data.pop(key, None)
                    
                return await show_final_confirmation(update, context, zone_info_text)
            else:
                await update.message.reply_text(
                    "❌ Не удалось создать зону. Продолжаем без зоны.",
                    reply_markup=ReplyKeyboardRemove()
                )
                context.user_data["game_zone"] = "auto"
                zone_info_text = "Игра будет использовать зону района по умолчанию"
                return await show_final_confirmation(update, context, zone_info_text)
                
        except Exception as e:
            logger.error(f"Ошибка создания зоны: {e}")
            await update.message.reply_text(
                f"❌ Ошибка создания зоны: {str(e)}\nПродолжаем без зоны.",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data["game_zone"] = "auto"
            zone_info_text = "Игра будет использовать зону района по умолчанию"
            return await show_final_confirmation(update, context, zone_info_text)
            
    elif confirmation == "❌ Нет, изменить":
        # Возвращаемся к вводу названия зоны
        await update.message.reply_text(
            "Введите название зоны заново:",
            reply_markup=ReplyKeyboardRemove()
        )
        return CREATE_ZONE_NAME
        
    elif confirmation == "⚙️ Отменить зону (без зоны)":
        context.user_data["game_zone"] = "auto"
        zone_info_text = "Игра будет использовать зону района по умолчанию"
        return await show_final_confirmation(update, context, zone_info_text)
    
    else:
        await update.message.reply_text(
            "❌ Неизвестный выбор. Используйте кнопки."
        )
        return CREATE_ZONE_CONFIRM

async def show_final_confirmation(update: Update, context: CallbackContext, zone_info_text: str) -> int:
    """Показ финального подтверждения создания игры"""
    # Собираем всю информацию для подтверждения
    district = context.user_data["game_district"]
    game_datetime = context.user_data["game_datetime"]
    max_participants = context.user_data["max_participants"]
    max_drivers = context.user_data["max_drivers"]
    max_seekers = max_participants - max_drivers
    description = context.user_data.get("description")
    
    confirmation_text = (
        "📋 <b>Подтверждение создания игры</b>\n\n"
        f"📍 <b>Район:</b> {district}\n"
        f"⏰ <b>Дата и время:</b> {game_datetime.strftime('%d.%m.%Y %H:%M')}\n"
        f"👥 <b>Максимум участников:</b> {max_participants}\n"
        f"🚗 <b>Водители:</b> {max_drivers}\n"
        f"🔍 <b>Искатели:</b> {max_seekers}\n"
        f"🗺️ <b>Игровая зона:</b> {zone_info_text}\n"
    )
    
    if description:
        confirmation_text += f"📝 <b>Описание:</b>\n{description}\n\n"
    
    confirmation_text += "Все верно? Создать игру?"
    
    keyboard = ReplyKeyboardMarkup([
        ["✅ Да, создать игру", "❌ Нет, отменить"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        confirmation_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return CREATE_CONFIRM

async def process_confirmation(update: Update, context: CallbackContext) -> int:
    """Обработка подтверждения создания игры"""
    confirmation = update.message.text
    
    if confirmation != "✅ Да, создать игру":
        await update.message.reply_text(
            "❌ Создание игры отменено.",
            reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
        )
        return ConversationHandler.END
    
    telegram_id = update.effective_user.id
    district = context.user_data["game_district"]
    game_datetime = context.user_data["game_datetime"]
    max_participants = context.user_data["max_participants"]
    max_drivers = context.user_data["max_drivers"]
    description = context.user_data.get("description")
    game_zone = context.user_data.get("game_zone")
    
    # Получаем пользователя из базы данных по telegram_id
    user, _ = UserService.get_user_by_telegram_id(telegram_id)
    if not user:
        await update.message.reply_text(
            "❌ Ошибка: пользователь не найден в базе данных.",
            reply_markup=get_admin_or_main_keyboard(telegram_id, True)
        )
        return ConversationHandler.END
    
    # Создаем игру, используя правильный user.id
    try:
        game = GameService.create_game(
            district=district,
            max_participants=max_participants,
            max_drivers=max_drivers,
            scheduled_at=game_datetime,
            creator_id=user.id,  # Используем user.id вместо telegram_id
            description=description
        )
        db=None
        
        # Обработка игровой зоны
        zone_result_text = ""
        if game_zone == "auto":
            # Автоматически устанавливаем зону района по умолчанию
            if LocationService.auto_set_game_zone_from_district(game):
                zone_result_text = f"\n🗺️ Автоматически установлена зона района по умолчанию"
            else:
                zone_result_text = f"\n⚠️ Зона района не найдена, игра без зоны"
                
        elif isinstance(game_zone, int):
            # Устанавливаем выбранную зону
            zone = ZoneManagementService.get_zone_by_id(game_zone)
            if zone:
                game.set_game_zone(zone.center_lat, zone.center_lon, zone.radius)
                # Сохраняем изменения
                from src.models.base import get_db
                db_generator = get_db()
                db = next(db_generator)
                db.add(game)
                db.commit()
                zone_result_text = f"\n🗺️ Установлена зона: {zone.zone_name}"
               
            else:
                zone_result_text = f"\n⚠️ Выбранная зона не найдена, игра без зоны"
        else:
            zone_result_text = f"\n⚠️ Неизвестная зона, игра без зоны"
        
        max_seekers = max_participants - max_drivers
        success_text = (
            f"✅ <b>Игра успешно создана!</b>\n\n"
            f"ID игры: {game.id}\n"
            f"Район: {game.district}\n"
            f"Дата и время: {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"Участников: {game.max_participants} (🚗 {game.max_drivers} водителей, 🔍 {max_seekers} искателей)"
            f"{zone_result_text}\n\n"
            f"Используйте /admingames для управления играми."
        )
        if db:
            db.close()
        
        
        await update.message.reply_text(
            success_text,
            reply_markup=get_admin_or_main_keyboard(telegram_id, True),
            parse_mode="HTML"
        )
    except ValueError as e:
        await update.message.reply_text(
            f"❌ Ошибка при создании игры: {str(e)}",
            reply_markup=get_admin_or_main_keyboard(telegram_id, True)
        )
    
    # Очищаем данные пользователя
    context.user_data.clear()
    
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    """Отмена создания игры"""
    await update.message.reply_text(
        "❌ Создание игры отменено.",
        reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
    )
    
    # Очищаем данные пользователя
    context.user_data.clear()
    
    return ConversationHandler.END

# Обработчик текстовых сообщений из админ-меню
async def handle_admin_text(update: Update, context: CallbackContext) -> None:
    """Обработчик текстовых сообщений из админ-меню"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        return
    
    if text == "📋 Список игр":
        return await admin_games_command(update, context)
    elif text == "🏙️ Управление районами":
        return await manage_districts_command(update, context)
    elif text == "👤 Управление ролями":
        return await manage_roles_command(update, context)
    elif text == "📋 Редактировать правила":
        return await edit_rules_command(update, context)
    elif text == "⚙️ Настройки игры":
        return await game_settings_command(update, context)
    elif text == "« Назад":
        # Возвращаем в главное меню
        is_admin = UserService.is_admin(user_id)
        await update.message.reply_text(
            "Вы вернулись в главное меню. Выберите действие:",
            reply_markup=get_admin_or_main_keyboard(user_id, False)
        )
        return
    
    # Остальные команды обрабатываются ConversationHandler'ами
    # Если не найден обработчик, возвращаем None, чтобы продолжить цепочку обработчиков
    return None



# Обработчик для создания игры
create_game_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("creategame", create_game_command),
        # Добавляем обработчик для текстовой кнопки "🎮 Создать игру"
        MessageHandler(
            filters.TEXT & filters.Regex(r"^🎮 Создать игру$") & ~filters.COMMAND,
            create_game_command
        )
    ],
    states={
        CREATE_DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_district)],
        CREATE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_date)],
        CREATE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_time)],
        CREATE_MAX_PARTICIPANTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_max_participants)],
        CREATE_MAX_DRIVERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_max_drivers)],
        CREATE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_description)],
        CREATE_ZONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_selection)],
        CREATE_ZONE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_name)],
        CREATE_ZONE_COORDINATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_coordinates)],
        CREATE_ZONE_RADIUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_radius)],
        CREATE_ZONE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_confirmation)],
        CREATE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_confirmation)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)


async def manage_districts_command(update: Update, context: CallbackContext) -> int:
    """Обработчик управления районами"""
    user_id = update.effective_user.id
    
    if not UserService.is_admin(user_id):
        await update.message.reply_text(
            "У вас нет прав доступа к этой команде.",
            reply_markup=get_admin_or_main_keyboard(user_id, True)
        )
        return ConversationHandler.END
    
    districts = SettingsService.get_all_districts()
    active_districts = [d for d in districts if d.is_active]
    inactive_districts = [d for d in districts if not d.is_active]
    
    active_text = "\n".join([f"• {district.name}" for district in active_districts])
    inactive_text = "\n".join([f"• {district.name}" for district in inactive_districts]) if inactive_districts else "Нет"
    
    keyboard = ReplyKeyboardMarkup([
        ["➕ Добавить район", "❌ Удалить район"],
        ["🔄 Восстановить район", "📋 Показать все"],
        ["« Назад в админку"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        f"🏙️ <b>Управление районами</b>\n\n"
        f"<b>Активные районы:</b>\n{active_text}\n\n"
        f"<b>Деактивированные:</b>\n{inactive_text}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return DISTRICT_ACTION

async def manage_roles_command(update: Update, context: CallbackContext) -> int:
    """Обработчик управления ролями"""
    user_id = update.effective_user.id
    
    if not UserService.is_admin(user_id):
        await update.message.reply_text(
            "У вас нет прав доступа к этой команде.",
            reply_markup=get_admin_or_main_keyboard(user_id, True)
        )
        return ConversationHandler.END
    
    roles = SettingsService.get_available_roles()
    
    keyboard = ReplyKeyboardMarkup([
        ["📝 Изменить отображение роли"],
        ["« Назад в админку"]
    ], resize_keyboard=True)
    
    roles_text = "\n".join([f"• {role}" for role in roles])
    
    await update.message.reply_text(
        f"👤 <b>Управление ролями</b>\n\n"
        f"<b>Доступные роли:</b>\n{roles_text}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ROLE_ACTION

async def role_action_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик действий с ролями"""
    text = update.message.text
    
    if text == "📝 Изменить отображение роли":
        roles = SettingsService.get_available_roles()
        keyboard = ReplyKeyboardMarkup(
            [[role] for role in roles] + [["« Отмена"]],
            resize_keyboard=True
        )
        await update.message.reply_text(
            "Выберите роль для изменения отображения:",
            reply_markup=keyboard
        )
        return EDIT_ROLE_DISPLAY
    elif text == "« Назад в админку":
        return await admin_command(update, context)
    
    await update.message.reply_text(
        "Пожалуйста, выберите действие из меню.",
        reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
    )
    return ConversationHandler.END

async def edit_role_display_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик изменения отображения роли"""
    role_display = update.message.text.strip()
    
    if role_display == "« Отмена":
        return await manage_roles_command(update, context)
    
    # Сохраняем выбранную роль для редактирования
    context.user_data["editing_role"] = role_display
    
    await update.message.reply_text(
        f"Введите новое отображаемое имя для роли {role_display}:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ENTER_NEW_ROLE_DISPLAY

async def enter_new_role_display_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик ввода нового отображаемого имени роли"""
    new_display = update.message.text.strip()
    old_display = context.user_data.get("editing_role")
    
    if not old_display:
        await update.message.reply_text(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
        )
        return ConversationHandler.END
    
    # Получаем роль из старого отображения
    role = SettingsService.get_role_from_display_name(old_display)
    if not role:
        await update.message.reply_text(
            "Не удалось найти роль. Попробуйте снова.",
            reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
        )
        return ConversationHandler.END
    
    # Обновляем отображение роли
    success = SettingsService.update_role_display(role, new_display)
    
    if success:
        await update.message.reply_text(
            f"✅ Отображение роли успешно изменено!\n"
            f"Было: {old_display}\n"
            f"Стало: {new_display}"
        )
    else:
        await update.message.reply_text(
            "❌ Произошла ошибка при обновлении отображения роли."
        )
    
    # Очищаем временные данные
    if "editing_role" in context.user_data:
        del context.user_data["editing_role"]
    
    return await manage_roles_command(update, context)

# Обработчики для районов
async def district_action_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик действий с районами"""
    text = update.message.text
    
    if text == "➕ Добавить район":
        await update.message.reply_text(
            "Введите название нового района:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_DISTRICT_NAME
    elif text == "❌ Удалить район":
        districts = SettingsService.get_districts()
        if not districts:
            await update.message.reply_text(
                "Нет активных районов для удаления.",
                reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
            )
            return ConversationHandler.END
        
        keyboard = ReplyKeyboardMarkup(
            [[district] for district in districts] + [["« Отмена"]],
            resize_keyboard=True
        )
        await update.message.reply_text(
            "Выберите район для деактивации:",
            reply_markup=keyboard
        )
        return REMOVE_DISTRICT_NAME
    elif text == "🔄 Восстановить район":
        all_districts = SettingsService.get_all_districts()
        inactive_districts = [d.name for d in all_districts if not d.is_active]
        
        if not inactive_districts:
            await update.message.reply_text(
                "Нет деактивированных районов для восстановления.",
                reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
            )
            return ConversationHandler.END
        
        keyboard = ReplyKeyboardMarkup(
            [[district] for district in inactive_districts] + [["« Отмена"]],
            resize_keyboard=True
        )
        await update.message.reply_text(
            "Выберите район для восстановления:",
            reply_markup=keyboard
        )
        context.user_data["restore_district"] = True
        return REMOVE_DISTRICT_NAME
    elif text == "« Назад в админку":
        return await admin_command(update, context)
    
    return DISTRICT_ACTION

async def add_district_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик добавления нового района"""
    district_name = update.message.text.strip()
    
    if len(district_name) < 2:
        await update.message.reply_text(
            "Название района должно содержать минимум 2 символа. Попробуйте еще раз:"
        )
        return ADD_DISTRICT_NAME
    
    success = SettingsService.add_district(district_name)
    
    if success:
        await update.message.reply_text(
            f"✅ Район '{district_name}' успешно добавлен!"
        )
    else:
        await update.message.reply_text(
            f"❌ Район '{district_name}' уже существует или произошла ошибка."
        )
    
    # Возвращаемся к экрану управления районами
    return await manage_districts_command(update, context)

async def remove_district_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик удаления/восстановления района"""
    district_name = update.message.text.strip()
    
    if district_name == "« Отмена":
        # Возвращаемся к управлению районами
        return await manage_districts_command(update, context)
    
    restore_mode = context.user_data.get("restore_district", False)
    
    if restore_mode:
        # Восстанавливаем район
        success = SettingsService.add_district(district_name)  # Функция сама проверит и восстановит
        action = "восстановлен"
    else:
        # Деактивируем район
        success = SettingsService.remove_district(district_name)
        action = "деактивирован"
    
    if success:
        await update.message.reply_text(
            f"✅ Район '{district_name}' успешно {action}!"
        )
    else:
        await update.message.reply_text(
            f"❌ Не удалось обработать район '{district_name}'."
        )
    
    # Очищаем флаг восстановления
    if "restore_district" in context.user_data:
        del context.user_data["restore_district"]
    
    # Возвращаемся к экрану управления районами
    return await manage_districts_command(update, context)


async def edit_rules_command(update: Update, context: CallbackContext) -> int:
    """Начало редактирования правил"""
    user_id = update.effective_user.id
    
    if not UserService.is_admin(user_id):
        await update.message.reply_text(
            "У вас нет прав доступа к этой команде.",
            reply_markup=get_admin_or_main_keyboard(user_id, True)
        )
        return ConversationHandler.END
    
    current_rules = SettingsService.get_game_rules()
    
    await update.message.reply_text(
        f"📋 <b>Редактирование правил игры</b>\n\n"
        f"<b>Текущие правила:</b>\n\n{current_rules}\n\n"
        f"Отправьте новый текст правил или /cancel для отмены:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return EDIT_RULES

async def process_new_rules(update: Update, context: CallbackContext) -> int:
    """Обработка новых правил"""
    new_rules = update.message.text
    user_id = update.effective_user.id
    
    # Сохраняем новые правила
    success = SettingsService.update_game_rules(new_rules)
    
    if success:
        await update.message.reply_text(
            "✅ <b>Правила успешно обновлены!</b>\n\n"
            "Новые правила будут показываться при регистрации пользователей.",
            reply_markup=get_admin_or_main_keyboard(user_id, True),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "❌ <b>Ошибка при обновлении правил.</b>\n\n"
            "Попробуйте еще раз или обратитесь к разработчику.",
            reply_markup=get_admin_or_main_keyboard(user_id, True),
            parse_mode="HTML"
        )
    
    return ConversationHandler.END

async def cancel_admin_operation(update: Update, context: CallbackContext) -> int:
    """Универсальная отмена админской операции"""
    user_id = update.effective_user.id
    
    # Возвращаем админскую клавиатуру
    admin_keyboard = get_admin_or_main_keyboard(user_id, True)
    
    await update.message.reply_text(
        "❌ Операция отменена.\n\n🔑 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=admin_keyboard,
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


# Обработчик для редактирования правил
edit_rules_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.TEXT & filters.Regex(r"^📋 Редактировать правила$") & ~filters.COMMAND,
            edit_rules_command
        )
    ],
    states={
        EDIT_RULES: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_rules)]
    },
    fallbacks=[CommandHandler("cancel", cancel_admin_operation)]
)

# Обработчик для управления районами
districts_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.TEXT & filters.Regex(r"^🏙️ Управление районами$") & ~filters.COMMAND,
            manage_districts_command
        )
    ],
    states={
        DISTRICT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, district_action_handler)],
        ADD_DISTRICT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_district_handler)],
        REMOVE_DISTRICT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_district_handler)]
    },
    fallbacks=[CommandHandler("cancel", cancel_admin_operation)]
)

# Обработчик для управления ролями
roles_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.TEXT & filters.Regex(r"^👤 Управление ролями$") & ~filters.COMMAND,
            manage_roles_command
        )
    ],
    states={
        ROLE_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, role_action_handler)],
        EDIT_ROLE_DISPLAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_role_display_handler)],
        ENTER_NEW_ROLE_DISPLAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_new_role_display_handler)]
    },
    fallbacks=[CommandHandler("cancel", cancel_admin_operation)]
)

# Обработчик для inline редактирования игры

async def process_datetime_edit(update: Update, context: CallbackContext) -> int:
    """Обработка нового значения даты и времени"""
    game_id = context.user_data.get("edit_game_id")
    if not game_id:
        await update.message.reply_text("❌ Ошибка: игра не найдена.")
        return ConversationHandler.END
    
    datetime_text = update.message.text.strip()
    
    try:
        # Парсим дату и время
        new_datetime = datetime.strptime(datetime_text, "%d.%m.%Y %H:%M")
        
        # Применяем изменение
        success = GameService.update_game(game_id, scheduled_at=new_datetime)
        
        if success:
            await update.message.reply_text(
                f"✅ <b>Дата и время успешно изменены!</b>\n\n"
                f"Новые дата и время: <b>{new_datetime.strftime('%d.%m.%Y %H:%M')}</b>",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Не удалось изменить дату и время.</b>",
                parse_mode="HTML"
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты и времени. Используйте формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 25.12.2024 18:30"
        )
        return EDIT_GAME_DATETIME_VALUE
    
    # Очищаем данные
    context.user_data.clear()
    return ConversationHandler.END

async def process_description_edit(update: Update, context: CallbackContext) -> int:
    """Обработка нового описания"""
    game_id = context.user_data.get("edit_game_id")
    if not game_id:
        await update.message.reply_text("❌ Ошибка: игра не найдена.")
        return ConversationHandler.END
    
    description_text = update.message.text.strip()
    
    # Если отправлен -, удаляем описание
    if description_text == "-":
        description_text = None
    
    # Применяем изменение
    success = GameService.update_game(game_id, description=description_text)
    
    if success:
        if description_text:
            await update.message.reply_text(
                f"✅ <b>Описание успешно изменено!</b>\n\n"
                f"Новое описание: <i>{description_text}</i>",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"✅ <b>Описание успешно удалено!</b>",
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text(
            f"❌ <b>Не удалось изменить описание.</b>",
            parse_mode="HTML"
        )
    
    # Очищаем данные
    context.user_data.clear()
    return ConversationHandler.END

async def set_district_value(update: Update, context: CallbackContext) -> None:
    """Обработчик применения нового района"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(SET_DISTRICT_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    new_district = match.group(2)
    
    # Применяем изменение
    success = GameService.update_game(game_id, district=new_district)
    
    if success:
        await query.edit_message_text(
            f"✅ <b>Район успешно изменен!</b>\n\n"
            f"Новый район: <b>{new_district}</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")],
                [InlineKeyboardButton("« К управлению игрой", callback_data=f"admin_game_{game_id}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Не удалось изменить район.</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")
            ]]),
            parse_mode="HTML"
        )

async def set_participants_value(update: Update, context: CallbackContext) -> None:
    """Обработчик применения нового количества участников"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(SET_PARTICIPANTS_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    new_count = int(match.group(2))
    
    # Применяем изменение
    success = GameService.update_game(game_id, max_participants=new_count)
    
    if success:
        await query.edit_message_text(
            f"✅ <b>Количество участников успешно изменено!</b>\n\n"
            f"Новое количество: <b>{new_count}</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")],
                [InlineKeyboardButton("« К управлению игрой", callback_data=f"admin_game_{game_id}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Не удалось изменить количество участников.</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")
            ]]),
            parse_mode="HTML"
        )

async def set_drivers_value(update: Update, context: CallbackContext) -> None:
    """Обработчик применения нового количества водителей"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(SET_DRIVERS_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    new_drivers = int(match.group(2))
    
    # Применяем изменение
    success = GameService.update_game(game_id, max_drivers=new_drivers)
    
    if success:
        game = GameService.get_game_by_id(game_id)
        seekers = game.max_participants - new_drivers
        await query.edit_message_text(
            f"✅ <b>Количество водителей успешно изменено!</b>\n\n"
            f"Новое распределение: <b>{new_drivers} водителей, {seekers} искателей</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")],
                [InlineKeyboardButton("« К управлению игрой", callback_data=f"admin_game_{game_id}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Не удалось изменить количество водителей.</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к редактированию", callback_data=f"edit_game_{game_id}")
            ]]),
            parse_mode="HTML"
        )

edit_game_fields_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(edit_datetime_button, pattern=EDIT_DATETIME_PATTERN),
        CallbackQueryHandler(edit_description_button, pattern=EDIT_DESCRIPTION_PATTERN)
    ],
    states={
        EDIT_GAME_DATETIME_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_datetime_edit)],
        EDIT_GAME_DESCRIPTION_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_description_edit)]
    },
    fallbacks=[CommandHandler("cancel", cancel_admin_operation)]
)

# =============================================================================
# НОВЫЕ ОБРАБОТЧИКИ ДЛЯ НАСТРОЕК ИГРЫ И РУЧНОГО УПРАВЛЕНИЯ
# =============================================================================

async def game_settings_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды настроек игры"""
    user_id = update.effective_user.id
    
    if not UserService.is_admin(user_id):
        await update.message.reply_text(
            "У вас нет прав доступа к этой команде.",
            reply_markup=get_admin_or_main_keyboard(user_id, True)
        )
        return
    
    settings = GameSettingsService.get_settings()
    keyboard = get_game_settings_keyboard(settings)
    
    mode_text = "🔴 Ручной" if settings.manual_control_mode else "🟢 Автоматический"
    
    settings_text = (
        f"⚙️ <b>Настройки игры</b>\n\n"
        f"🎮 <b>Режим управления:</b> {mode_text}\n\n"
        f"📊 <b>Основные настройки:</b>\n"
        f"• Автостарт игры: {'✅' if settings.auto_start_game else '❌'}\n"
        f"• Автораспределение ролей: {'✅' if settings.auto_assign_roles else '❌'}\n"
        f"• Автостарт фазы пряток: {'✅' if settings.auto_start_hiding else '❌'}\n"
        f"• Автостарт фазы поиска: {'✅' if settings.auto_start_searching else '❌'}\n"
        f"• Автозавершение игры: {'✅' if settings.auto_end_game else '❌'}\n\n"
        f"⏱ <b>Временные настройки:</b>\n"
        f"• Фаза пряток: {settings.hiding_phase_duration} мин\n"
        f"• Фаза поиска: {settings.searching_phase_duration} мин\n"
        f"• Мин. участников: {settings.min_participants_to_start}\n\n"
        f"Выберите раздел для настройки:"
    )
    
    await update.message.reply_text(
        settings_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def toggle_manual_control(update: Update, context: CallbackContext) -> None:
    """Переключение режима ручного управления"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    settings = GameSettingsService.get_settings()
    new_mode = not settings.manual_control_mode
    
    success = GameSettingsService.update_settings(manual_control_mode=new_mode)
    
    if success:
        settings = GameSettingsService.get_settings()  # Обновляем данные
        keyboard = get_game_settings_keyboard(settings)
        
        mode_text = "🔴 Ручной" if new_mode else "🟢 Автоматический"
        action_text = "включен" if new_mode else "выключен"
        
        settings_text = (
            f"⚙️ <b>Настройки игры</b>\n\n"
            f"🎮 <b>Режим управления:</b> {mode_text}\n"
            f"✅ Режим ручного управления {action_text}\n\n"
            f"📊 <b>Основные настройки:</b>\n"
            f"• Автостарт игры: {'✅' if settings.auto_start_game else '❌'}\n"
            f"• Автораспределение ролей: {'✅' if settings.auto_assign_roles else '❌'}\n"
            f"• Автостарт фазы пряток: {'✅' if settings.auto_start_hiding else '❌'}\n"
            f"• Автостарт фазы поиска: {'✅' if settings.auto_start_searching else '❌'}\n"
            f"• Автозавершение игры: {'✅' if settings.auto_end_game else '❌'}\n\n"
            f"⏱ <b>Временные настройки:</b>\n"
            f"• Фаза пряток: {settings.hiding_phase_duration} мин\n"
            f"• Фаза поиска: {settings.searching_phase_duration} мин\n"
            f"• Мин. участников: {settings.min_participants_to_start}\n\n"
            f"Выберите раздел для настройки:"
        )
        
        await query.edit_message_text(
            settings_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await query.answer("❌ Ошибка при изменении настроек", show_alert=True)

async def automation_settings_button(update: Update, context: CallbackContext) -> None:
    """Обработчик настроек автоматизации"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    settings = GameSettingsService.get_settings()
    keyboard = get_automation_settings_keyboard(settings)
    
    automation_text = (
        f"⚙️ <b>Настройки автоматизации</b>\n\n"
        f"🎮 <b>Автоматические процессы:</b>\n\n"
        f"{'✅' if settings.auto_start_game else '❌'} <b>Автостарт игры</b>\n"
        f"Автоматический запуск игры по расписанию\n\n"
        f"{'✅' if settings.auto_assign_roles else '❌'} <b>Автораспределение ролей</b>\n"
        f"Автоматическое назначение ролей участникам\n\n"
        f"{'✅' if settings.auto_start_hiding else '❌'} <b>Автостарт фазы пряток</b>\n"
        f"Автоматический переход к фазе пряток\n\n"
        f"{'✅' if settings.auto_start_searching else '❌'} <b>Автостарт фазы поиска</b>\n"
        f"Автоматический переход к фазе поиска\n\n"
        f"{'✅' if settings.auto_end_game else '❌'} <b>Автозавершение игры</b>\n"
        f"Автоматическое завершение игры по времени\n\n"
        f"💡 <i>Нажмите на настройку для изменения</i>"
    )
    
    await query.edit_message_text(
        automation_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def toggle_automation_setting(update: Update, context: CallbackContext) -> None:
    """Переключение настройки автоматизации"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Определяем какую настройку переключить
    setting_map = {
        "toggle_auto_start_game": "auto_start_game",
        "toggle_auto_assign_roles": "auto_assign_roles", 
        "toggle_auto_start_hiding": "auto_start_hiding",
        "toggle_auto_start_searching": "auto_start_searching",
        "toggle_auto_end_game": "auto_end_game"
    }
    
    setting_name = setting_map.get(query.data)
    if not setting_name:
        return
    
    settings = GameSettingsService.get_settings()
    current_value = getattr(settings, setting_name)
    new_value = not current_value
    
    success = GameSettingsService.update_settings(**{setting_name: new_value})
    
    if success:
        # Обновляем отображение
        await automation_settings_button(update, context)
    else:
        await query.answer("❌ Ошибка при изменении настроек", show_alert=True)

async def manual_control_button(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки ручного управления игрой"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Извлекаем ID игры
    match = re.match(r"manual_control_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Получаем информацию о игре для управления
    control_info = ManualGameControlService.get_game_control_info(game_id)
    
    if not control_info["success"]:
        await query.edit_message_text(
            f"❌ {control_info['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=f"admin_game_{game_id}")
            ]])
        )
        return
    
    game_info = control_info["game"]
    participants = control_info["participants"]
    stats = control_info["statistics"]
    
    # Формируем текст с информацией об игре
    status_emoji = {
        "recruiting": "📝",
        "upcoming": "⏰", 
        "hiding_phase": "🙈",
        "searching_phase": "🔍",
        "completed": "✅",
        "canceled": "❌"
    }
    
    control_text = (
        f"🎮 <b>Ручное управление игрой #{game_id}</b>\n\n"
        f"{status_emoji.get(game_info['status'], '❓')} <b>Статус:</b> {game_info['status']}\n"
        f"📍 <b>Район:</b> {game_info['district']}\n"
        f"⏰ <b>Время:</b> {datetime.fromisoformat(game_info['scheduled_at']).strftime('%d.%m.%Y %H:%M')}\n"
        f"👥 <b>Участники:</b> {game_info['participants_count']}/{game_info['max_participants']}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"🚗 Водители: {stats['total_drivers']} (найдено: {stats['found_drivers']})\n"
        f"🔍 Искатели: {stats['total_seekers']}\n"
        f"⏳ Осталось найти: {stats['remaining_drivers']}\n\n"
    )
    
    if participants:
        control_text += "👥 <b>Участники:</b>\n"
        for p in participants[:5]:  # Показываем первых 5
            role_emoji = "🚗" if p["role"] == "driver" else "🔍"
            status_emoji = "✅" if p["is_found"] else "⏳"
            control_text += f"{role_emoji}{status_emoji} {p['user_name']}\n"
        
        if len(participants) > 5:
            control_text += f"... и еще {len(participants) - 5}\n"
        control_text += "\n"
    
    control_text += "Выберите действие:"
    
    keyboard = get_manual_control_keyboard(game_id, game_info["status"], participants)
    
    await query.edit_message_text(
        control_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def manual_assign_roles_button(update: Update, context: CallbackContext) -> None:
    """Ручное распределение ролей"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"manual_assign_roles_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Используем существующий сервис для распределения ролей
    roles = GameService.assign_roles(game_id)
    
    if roles:
        await query.edit_message_text(
            f"✅ <b>Роли успешно распределены!</b>\n\n"
            f"🎲 Роли назначены {len(roles)} участникам",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"manual_control_{game_id}")
            ]]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Не удалось распределить роли</b>\n\n"
            f"Возможно, в игре недостаточно участников",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"manual_control_{game_id}")
            ]]),
            parse_mode="HTML"
        )

async def manual_start_hiding_button(update: Update, context: CallbackContext) -> None:
    """Ручной запуск фазы пряток"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"manual_start_hiding_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    result = ManualGameControlService.manual_start_hiding_phase(game_id, user_id)
    
    if result["success"]:
        await query.edit_message_text(
            f"✅ <b>{result['message']}</b>\n\n"
            f"🙈 Фаза пряток началась!\n"
            f"⏰ Время начала: {datetime.fromisoformat(result['started_at']).strftime('%H:%M:%S')}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"manual_control_{game_id}")
            ]]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"manual_control_{game_id}")
            ]]),
            parse_mode="HTML"
        )

async def manual_start_searching_button(update: Update, context: CallbackContext) -> None:
    """Ручной запуск фазы поиска"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"manual_start_searching_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    result = ManualGameControlService.manual_start_searching_phase(game_id, user_id)
    
    if result["success"]:
        await query.edit_message_text(
            f"✅ <b>{result['message']}</b>\n\n"
            f"🔍 Фаза поиска началась!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"manual_control_{game_id}")
            ]]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"manual_control_{game_id}")
            ]]),
            parse_mode="HTML"
        )

async def manual_end_game_button(update: Update, context: CallbackContext) -> None:
    """Ручное завершение игры"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"manual_end_game_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    result = ManualGameControlService.manual_end_game(game_id, user_id, "Завершено администратором вручную")
    
    if result["success"]:
        await query.edit_message_text(
            f"✅ <b>{result['message']}</b>\n\n"
            f"🏁 Игра завершена!\n"
            f"⏰ Время завершения: {datetime.fromisoformat(result['ended_at']).strftime('%H:%M:%S')}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ К списку игр", callback_data="back_to_admin_games")
            ]]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"manual_control_{game_id}")
            ]]),
            parse_mode="HTML"
        )

async def manage_participants_button(update: Update, context: CallbackContext) -> None:
    """Управление участниками игры"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"manage_participants_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    control_info = ManualGameControlService.get_game_control_info(game_id)
    
    if not control_info["success"]:
        await query.edit_message_text(f"❌ {control_info['error']}")
        return
    
    participants = control_info["participants"]
    keyboard = get_participants_management_keyboard(game_id, participants)
    
    participants_text = (
        f"👥 <b>Управление участниками игры #{game_id}</b>\n\n"
        f"Всего участников: {len(participants)}\n\n"
        f"🚗 - Водитель, 🔍 - Искатель\n"
        f"✅ - Найден, ⏳ - В игре\n\n"
        f"Выберите участника для управления:"
    )
    
    await query.edit_message_text(
        participants_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def manage_individual_participant_button(update: Update, context: CallbackContext) -> None:
    """Управление конкретным участником игры"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"manage_participant_(\d+)_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    participant_id = int(match.group(2))
    
    # Получаем информацию об участнике
    control_info = ManualGameControlService.get_game_control_info(game_id)
    
    if not control_info["success"]:
        await query.edit_message_text(f"❌ {control_info['error']}")
        return
    
    # Ищем конкретного участника
    participant_info = None
    for participant in control_info["participants"]:
        if participant["id"] == participant_id:
            participant_info = participant
            break
    
    if not participant_info:
        await query.edit_message_text("❌ Участник не найден")
        return
    
    # Создаем клавиатуру с действиями для участника
    from src.keyboards.inline import get_participant_actions_keyboard
    keyboard = get_participant_actions_keyboard(game_id, participant_id, participant_info)
    
    role_emoji = "🚗" if participant_info.get("role") == "driver" else "🔍"
    status_emoji = "✅" if participant_info.get("is_found") else "⏳"
    
    participant_text = (
        f"👤 <b>Управление участником</b>\n\n"
        f"🎮 <b>Игра #{game_id}</b>\n"
        f"👤 <b>Участник:</b> {participant_info['user_name']}\n"
        f"🎭 <b>Роль:</b> {role_emoji} {participant_info.get('role', 'Не назначена')}\n"
        f"📊 <b>Статус:</b> {status_emoji} {'Найден' if participant_info.get('is_found') else 'В игре'}\n\n"
        f"Выберите действие:"
    )
    
    await query.edit_message_text(
        participant_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def change_participant_role_button(update: Update, context: CallbackContext) -> None:
    """Изменение роли участника"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"change_role_(\d+)_(\d+)_(driver|seeker)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    participant_id = int(match.group(2))
    new_role_str = match.group(3)
    
    from src.models.game import GameRole
    new_role = GameRole.DRIVER if new_role_str == "driver" else GameRole.SEEKER
    
    result = ManualGameControlService.reassign_participant_role(game_id, participant_id, new_role, user_id)
    
    if result["success"]:
        await query.edit_message_text(
            f"✅ <b>{result['message']}</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участнику", callback_data=f"manage_participant_{game_id}_{participant_id}"),
                InlineKeyboardButton("◀️ К участникам", callback_data=f"manage_participants_{game_id}")
            ]]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участнику", callback_data=f"manage_participant_{game_id}_{participant_id}")
            ]]),
            parse_mode="HTML"
        )

async def mark_participant_found_button(update: Update, context: CallbackContext) -> None:
    """Отметка участника как найденного"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"mark_found_(\d+)_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    participant_id = int(match.group(2))
    
    result = ManualGameControlService.manual_mark_participant_found(game_id, participant_id, user_id)
    
    if result["success"]:
        await query.edit_message_text(
            f"✅ <b>{result['message']}</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участнику", callback_data=f"manage_participant_{game_id}_{participant_id}"),
                InlineKeyboardButton("◀️ К участникам", callback_data=f"manage_participants_{game_id}")
            ]]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участнику", callback_data=f"manage_participant_{game_id}_{participant_id}")
            ]]),
            parse_mode="HTML"
        )

async def mark_participant_eliminated_button(update: Update, context: CallbackContext) -> None:
    """Отметка участника как выбывшего"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"mark_eliminated_(\d+)_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    participant_id = int(match.group(2))
    
    result = ManualGameControlService.manual_mark_participant_eliminated(game_id, participant_id, user_id)
    
    if result["success"]:
        await query.edit_message_text(
            f"✅ <b>{result['message']}</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участнику", callback_data=f"manage_participant_{game_id}_{participant_id}"),
                InlineKeyboardButton("◀️ К участникам", callback_data=f"manage_participants_{game_id}")
            ]]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участнику", callback_data=f"manage_participant_{game_id}_{participant_id}")
            ]]),
            parse_mode="HTML"
        )

async def unmark_participant_found_button(update: Update, context: CallbackContext) -> None:
    """Отмена отметки участника как найденного"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"unmark_found_(\d+)_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    participant_id = int(match.group(2))
    
    result = ManualGameControlService.manual_unmark_participant_found(game_id, participant_id, user_id)
    
    if result["success"]:
        await query.edit_message_text(
            f"✅ <b>{result['message']}</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участнику", callback_data=f"manage_participant_{game_id}_{participant_id}"),
                InlineKeyboardButton("◀️ К участникам", callback_data=f"manage_participants_{game_id}")
            ]]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участнику", callback_data=f"manage_participant_{game_id}_{participant_id}")
            ]]),
            parse_mode="HTML"
        )

async def add_participant_button(update: Update, context: CallbackContext) -> None:
    """Показать список доступных пользователей для добавления"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"add_participant_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Получаем список доступных пользователей
    available_users = ManualGameControlService.get_available_users_for_game(game_id)
    
    if not available_users:
        await query.edit_message_text(
            f"❌ <b>Нет доступных пользователей для добавления</b>\n\n"
            f"Все зарегистрированные пользователи уже участвуют в игре.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участникам", callback_data=f"manage_participants_{game_id}")
            ]]),
            parse_mode="HTML"
        )
        return
    
    # Создаем клавиатуру с доступными пользователями
    from src.keyboards.inline import get_available_users_keyboard
    keyboard = get_available_users_keyboard(game_id, available_users)
    
    await query.edit_message_text(
        f"➕ <b>Добавление участника в игру #{game_id}</b>\n\n"
        f"Доступно пользователей: {len(available_users)}\n\n"
        f"Выберите пользователя для добавления:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def confirm_add_participant_button(update: Update, context: CallbackContext) -> None:
    """Подтверждение добавления участника"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"confirm_add_participant_(\d+)_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    target_user_id = int(match.group(2))
    
    # Добавляем участника
    result = ManualGameControlService.add_participant_to_game(game_id, target_user_id, user_id)
    
    if result["success"]:
        await query.edit_message_text(
            f"✅ <b>{result['message']}</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 К списку участников", callback_data=f"manage_participants_{game_id}")],
                [InlineKeyboardButton("🎮 К управлению игрой", callback_data=f"manual_control_{game_id}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к добавлению", callback_data=f"add_participant_{game_id}")
            ]]),
            parse_mode="HTML"
        )

async def remove_participant_button(update: Update, context: CallbackContext) -> None:
    """Удаление участника из игры"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"remove_participant_(\d+)_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    participant_id = int(match.group(2))
    
    # Удаляем участника
    result = ManualGameControlService.remove_participant_from_game(game_id, participant_id, user_id)
    
    if result["success"]:
        await query.edit_message_text(
            f"✅ <b>{result['message']}</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 К списку участников", callback_data=f"manage_participants_{game_id}")],
                [InlineKeyboardButton("🎮 К управлению игрой", callback_data=f"manual_control_{game_id}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"❌ <b>Ошибка:</b> {result['error']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к участнику", callback_data=f"manage_participant_{game_id}_{participant_id}")
            ]]),
            parse_mode="HTML"
        )

async def choose_role_assignment_type_button(update: Update, context: CallbackContext) -> None:
    """Выбор типа распределения ролей (случайное или ручное)"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"choose_role_assignment_type_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Получаем информацию об игре
    game = GameService.get_game_by_id(game_id)
    if not game:
        await query.edit_message_text("❌ Игра не найдена")
        return
    
    participants_count = len(game.participants)
    
    # Создаем клавиатуру выбора типа
    from src.keyboards.inline import get_role_assignment_type_keyboard
    keyboard = get_role_assignment_type_keyboard(game_id)
    
    await query.edit_message_text(
        f"🎲 <b>Распределение ролей для игры #{game_id}</b>\n\n"
        f"👥 <b>Участников:</b> {participants_count}\n"
        f"🚗 <b>Максимум водителей:</b> {game.max_drivers}\n\n"
        f"Выберите способ распределения ролей:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def assign_roles_random_button(update: Update, context: CallbackContext) -> None:
    """Случайное распределение ролей"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"assign_roles_random_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Выполняем случайное распределение ролей
    roles = GameService.assign_roles(game_id)
    
    if not roles:
        await query.edit_message_text(
            "❌ Не удалось распределить роли. Возможно, в игре недостаточно участников.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад к выбору типа", callback_data=f"choose_role_assignment_type_{game_id}")
            ]])
        )
        return
    
    # Формируем сообщение с результатом
    game = GameService.get_game_by_id(game_id)
    roles_info = "\n".join([
        f"- {p.user.name}: {'🚗 Водитель' if p.role == GameRole.DRIVER else '🔍 Искатель'}" 
        for p in game.participants if p.role
    ])
    
    await query.edit_message_text(
        f"✅ <b>Роли распределены случайно!</b>\n\n"
        f"<b>Результат:</b>\n{roles_info}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"manual_control_{game_id}")
        ]]),
        parse_mode="HTML"
    )

async def assign_roles_manual_button(update: Update, context: CallbackContext) -> None:
    """Показать интерфейс ручного назначения ролей"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"assign_roles_manual_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Получаем информацию для ручного назначения ролей
    info = ManualGameControlService.get_manual_role_assignment_info(game_id)
    
    if not info["success"]:
        await query.edit_message_text(f"❌ {info['error']}")
        return
    
    participants = info["participants"]
    max_drivers = info["max_drivers"]
    
    # Формируем заголовок с информацией
    drivers_count = sum(1 for p in participants if p.get("current_role") == "driver")
    seekers_count = sum(1 for p in participants if p.get("current_role") == "seeker")
    unassigned_count = sum(1 for p in participants if not p.get("current_role"))
    
    header_text = (
        f"✋ <b>Ручное распределение ролей</b>\n\n"
        f"👥 <b>Участников:</b> {len(participants)}\n"
        f"🚗 <b>Водители:</b> {drivers_count}/{max_drivers}\n"
        f"🔍 <b>Искатели:</b> {seekers_count}\n"
        f"❓ <b>Без ролей:</b> {unassigned_count}\n\n"
        f"Нажмите на участника, чтобы назначить ему роль:"
    )
    
    from src.keyboards.inline import get_manual_role_assignment_keyboard
    keyboard = get_manual_role_assignment_keyboard(game_id, participants, max_drivers)
    
    await query.edit_message_text(
        header_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def edit_participant_role_button(update: Update, context: CallbackContext) -> None:
    """Показать меню редактирования роли конкретного участника"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"edit_participant_role_(\d+)_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    participant_id = int(match.group(2))
    
    # Получаем информацию о игре и участнике
    info = ManualGameControlService.get_manual_role_assignment_info(game_id)
    
    if not info["success"]:
        await query.edit_message_text(f"❌ {info['error']}")
        return
    
    # Находим конкретного участника
    participant = None
    for p in info["participants"]:
        if p["id"] == participant_id:
            participant = p
            break
    
    if not participant:
        await query.edit_message_text("❌ Участник не найден")
        return
    
    current_role = participant.get("current_role")
    participant_name = participant["user_name"]
    max_drivers = info["max_drivers"]
    current_driver_count = info["current_driver_count"]
    
    # Заголовок
    current_role_text = "Не назначена"
    if current_role == "driver":
        current_role_text = "🚗 Водитель"
    elif current_role == "seeker":
        current_role_text = "🔍 Искатель"
    
    header_text = (
        f"👤 <b>{participant_name}</b>\n\n"
        f"🎭 <b>Текущая роль:</b> {current_role_text}\n"
        f"🚗 <b>Водители в игре:</b> {current_driver_count}/{max_drivers}\n\n"
        f"Выберите новую роль для участника:"
    )
    
    from src.keyboards.inline import get_participant_role_edit_keyboard
    keyboard = get_participant_role_edit_keyboard(
        game_id, participant_id, participant_name, 
        current_role, max_drivers, current_driver_count
    )
    
    await query.edit_message_text(
        header_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def set_participant_role_button(update: Update, context: CallbackContext) -> None:
    """Установить роль участника"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"set_participant_role_(\d+)_(\d+)_(driver|seeker|none)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    participant_id = int(match.group(2))
    new_role_str = match.group(3)
    
    # Преобразуем роль
    db_generator = get_db()
    db = next(db_generator)
    
    try:
        participant = db.query(GameParticipant).filter(
            GameParticipant.game_id == game_id,
            GameParticipant.id == participant_id
        ).first()
        
        if not participant:
            await query.edit_message_text("❌ Участник не найден")
            return
        
        # Устанавливаем новую роль
        from src.models.game import GameRole
        if new_role_str == "driver":
            new_role = GameRole.DRIVER
        elif new_role_str == "seeker":
            new_role = GameRole.SEEKER
        else:  # "none"
            new_role = None
        
        # Проверяем лимиты для водителей
        if new_role == GameRole.DRIVER:
            game = participant.game
            current_drivers = db.query(GameParticipant).filter(
                GameParticipant.game_id == game_id,
                GameParticipant.role == GameRole.DRIVER,
                GameParticipant.id != participant_id  # Исключаем текущего участника
            ).count()
            
            if current_drivers >= game.max_drivers:
                await query.answer("❌ Достигнут лимит водителей!", show_alert=True)
                return
        
        old_role = participant.role
        participant.role = new_role
        db.commit()
        
        # Логируем изменение
        role_text = "убрана" if new_role is None else new_role.value
        logger.info(f"Админ {user_id} установил роль '{role_text}' участнику {participant_id} в игре {game_id}")
        
        # Показываем промежуточное сообщение с подтверждением
        participant_name = participant.user.name
        
        if new_role is None:
            status_text = f"✅ Роль участника <b>{participant_name}</b> убрана"
            status_emoji = "❓"
        elif new_role == GameRole.DRIVER:
            status_text = f"✅ <b>{participant_name}</b> назначен водителем 🚗"
            status_emoji = "🚗"
        else:  # SEEKER
            status_text = f"✅ <b>{participant_name}</b> назначен искателем 🔍"
            status_emoji = "🔍"
        
        # Показываем уведомление с анимацией
        await query.edit_message_text(
            f"{status_text}\n\n"
            f"⏳ Обновляем список участников...",
            parse_mode="HTML"
        )
        
        # Небольшая пауза для визуального эффекта
        await asyncio.sleep(1)
        
        # Возвращаемся к обновленному списку участников
        await _show_manual_role_assignment_interface(update, context, game_id)
        
    except Exception as e:
        logger.error(f"Ошибка при установке роли: {e}")
        db.rollback()
        await query.edit_message_text(
            f"❌ Ошибка при установке роли: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=f"assign_roles_manual_{game_id}")
            ]])
        )
    finally:
        db.close()

async def auto_fill_roles_button(update: Update, context: CallbackContext) -> None:
    """Автоматически заполнить оставшиеся роли"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"auto_fill_roles_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    db_generator = get_db()
    db = next(db_generator)
    
    try:
        # Получаем игру и участников без ролей
        from src.models.game import Game, GameRole
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            await query.edit_message_text("❌ Игра не найдена")
            return
        
        unassigned_participants = db.query(GameParticipant).filter(
            GameParticipant.game_id == game_id,
            GameParticipant.role.is_(None)
        ).all()
        
        if not unassigned_participants:
            await query.answer("✅ Все роли уже назначены!", show_alert=True)
            return
        
        # Подсчитываем текущих водителей
        current_drivers = db.query(GameParticipant).filter(
            GameParticipant.game_id == game_id,
            GameParticipant.role == GameRole.DRIVER
        ).count()
        
        # Определяем сколько еще можно назначить водителей
        max_new_drivers = game.max_drivers - current_drivers
        drivers_to_assign = min(max_new_drivers, len(unassigned_participants))
        
        # Назначаем роли
        import random
        random.shuffle(unassigned_participants)  # Случайный порядок
        
        assigned_count = 0
        
        # Назначаем водителей
        for participant in unassigned_participants[:drivers_to_assign]:
            participant.role = GameRole.DRIVER
            assigned_count += 1
        
        # Остальных делаем искателями
        for participant in unassigned_participants[drivers_to_assign:]:
            participant.role = GameRole.SEEKER
            assigned_count += 1
        
        db.commit()
        
        logger.info(f"Админ {user_id} автоматически назначил роли {assigned_count} участникам в игре {game_id}")
        
        # Показываем промежуточное сообщение с результатом автозаполнения
        await query.edit_message_text(
            f"⚡ <b>Автозаполнение завершено!</b>\n\n"
            f"✅ Назначено ролей: <b>{assigned_count}</b>\n"
            f"🚗 Новых водителей: <b>{drivers_to_assign}</b>\n"
            f"🔍 Новых искателей: <b>{len(unassigned_participants) - drivers_to_assign}</b>\n\n"
            f"⏳ Обновляем список участников...",
            parse_mode="HTML"
        )
        
        # Пауза для визуального эффекта
        await asyncio.sleep(1.5)
        
        # Возвращаемся к списку участников
        await _show_manual_role_assignment_interface(update, context, game_id)
        
    except Exception as e:
        logger.error(f"Ошибка при автозаполнении ролей: {e}")
        db.rollback()
        await query.edit_message_text(
            f"❌ Ошибка при автозаполнении: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=f"assign_roles_manual_{game_id}")
            ]])
        )
    finally:
        db.close()

async def reset_all_roles_button(update: Update, context: CallbackContext) -> None:
    """Сброс всех ролей участников"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"reset_all_roles_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Сбрасываем все роли
    db_generator = get_db()
    db = next(db_generator)
    
    try:
        participants = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).all()
        for participant in participants:
            participant.role = None
        
        db.commit()
        logger.info(f"Админ {user_id} сбросил все роли в игре {game_id}")
        
        # Показываем промежуточное сообщение с подтверждением
        roles_count = len(participants)
        await query.edit_message_text(
            f"🔄 <b>Все роли сброшены!</b>\n\n"
            f"✅ Очищено ролей: <b>{roles_count}</b>\n"
            f"❓ Все участники теперь без ролей\n\n"
            f"⏳ Обновляем список участников...",
            parse_mode="HTML"
        )
        
        # Пауза для визуального эффекта
        await asyncio.sleep(1)
        
        # Возвращаемся к интерфейсу ручного назначения
        await _show_manual_role_assignment_interface(update, context, game_id)
        
    except Exception as e:
        logger.error(f"Ошибка при сбросе ролей: {e}")
        db.rollback()
        await query.edit_message_text(
            f"❌ Ошибка при сбросе ролей: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=f"assign_roles_manual_{game_id}")
            ]])
        )
    finally:
        db.close()

async def confirm_manual_roles_button(update: Update, context: CallbackContext) -> None:
    """Подтверждение ручного распределения ролей"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(r"confirm_manual_roles_(\d+)", query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Получаем текущую информацию о ролях
    info = ManualGameControlService.get_manual_role_assignment_info(game_id)
    
    if not info["success"]:
        await query.edit_message_text(f"❌ {info['error']}")
        return
    
    # Формируем сообщение с результатом
    participants = info["participants"]
    drivers = [p for p in participants if p.get("current_role") == "driver"]
    seekers = [p for p in participants if p.get("current_role") == "seeker"]
    
    roles_info = ""
    if drivers:
        roles_info += "🚗 <b>Водители:</b>\n"
        for driver in drivers:
            roles_info += f"  - {driver['user_name']}\n"
    
    if seekers:
        roles_info += "\n🔍 <b>Искатели:</b>\n"
        for seeker in seekers:
            roles_info += f"  - {seeker['user_name']}\n"
    
    await query.edit_message_text(
        f"✅ <b>Роли успешно назначены вручную!</b>\n\n"
        f"{roles_info}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад к управлению", callback_data=f"manual_control_{game_id}")
        ]]),
        parse_mode="HTML"
    )

async def _show_manual_role_assignment_interface(update: Update, context: CallbackContext, game_id: int) -> None:
    """Helper функция для отображения интерфейса ручного назначения ролей по game_id"""
    query = update.callback_query
    
    try:
        # Получаем информацию для ручного назначения ролей
        info = ManualGameControlService.get_manual_role_assignment_info(game_id)
        
        if not info["success"]:
            await query.edit_message_text(f"❌ {info['error']}")
            return
        
        participants = info["participants"]
        max_drivers = info["max_drivers"]
        
        # Формируем заголовок с информацией
        drivers_count = sum(1 for p in participants if p.get("current_role") == "driver")
        seekers_count = sum(1 for p in participants if p.get("current_role") == "seeker")
        unassigned_count = sum(1 for p in participants if not p.get("current_role"))
        
        header_text = (
            f"✋ <b>Ручное распределение ролей</b>\n\n"
            f"👥 <b>Участников:</b> {len(participants)}\n"
            f"🚗 <b>Водители:</b> {drivers_count}/{max_drivers}\n"
            f"🔍 <b>Искатели:</b> {seekers_count}\n"
            f"❓ <b>Без ролей:</b> {unassigned_count}\n\n"
            f"Нажмите на участника, чтобы назначить ему роль:"
        )
        
        from src.keyboards.inline import get_manual_role_assignment_keyboard
        keyboard = get_manual_role_assignment_keyboard(game_id, participants, max_drivers)
        
        await query.edit_message_text(
            header_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в _show_manual_role_assignment_interface для игры {game_id}: {e}")
        await query.edit_message_text(
            f"❌ Ошибка при обновлении интерфейса: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=f"manual_control_{game_id}")
            ]])
    )

# =============================================================================
# КОНЕЦ НОВЫХ ОБРАБОТЧИКОВ
# =============================================================================

# Регистрация обработчиков для админ-функций
admin_handlers = [
    CommandHandler("admin", admin_command),
    CommandHandler("admingames", admin_games_command),
    CallbackQueryHandler(admin_game_button, pattern=ADMIN_GAME_PATTERN),
    CallbackQueryHandler(cancel_game_button, pattern=ADMIN_CANCEL_PATTERN),
    CallbackQueryHandler(start_game_button, pattern=ADMIN_START_PATTERN),
    CallbackQueryHandler(start_game_early_button, pattern=r"start_early_\d+"),
    CallbackQueryHandler(back_to_admin_games_button, pattern="back_to_admin_games"),
    CallbackQueryHandler(create_game_button, pattern="create_game"),
    CallbackQueryHandler(edit_game_inline_button, pattern=ADMIN_EDIT_GAME_PATTERN),
    # Обработчики для редактирования полей игры
    CallbackQueryHandler(edit_district_button, pattern=EDIT_DISTRICT_PATTERN),
    CallbackQueryHandler(edit_participants_button, pattern=EDIT_PARTICIPANTS_PATTERN),
    CallbackQueryHandler(edit_drivers_button, pattern=EDIT_DRIVERS_PATTERN),
    # Обработчики для применения изменений
    CallbackQueryHandler(set_district_value, pattern=SET_DISTRICT_PATTERN),
    CallbackQueryHandler(set_participants_value, pattern=SET_PARTICIPANTS_PATTERN),
    CallbackQueryHandler(set_drivers_value, pattern=SET_DRIVERS_PATTERN),
    
    # Новые обработчики для настроек игры
    CallbackQueryHandler(toggle_manual_control, pattern="toggle_manual_control"),
    CallbackQueryHandler(automation_settings_button, pattern="automation_settings"),
    CallbackQueryHandler(toggle_automation_setting, pattern=r"toggle_auto_(start_game|assign_roles|start_hiding|start_searching|end_game)"),
    
    # Новые обработчики для ручного управления игрой
    CallbackQueryHandler(manual_control_button, pattern=r"manual_control_\d+"),
    CallbackQueryHandler(manual_assign_roles_button, pattern=r"manual_assign_roles_\d+"),
    CallbackQueryHandler(manual_start_hiding_button, pattern=r"manual_start_hiding_\d+"),
    CallbackQueryHandler(manual_start_searching_button, pattern=r"manual_start_searching_\d+"),
    CallbackQueryHandler(manual_end_game_button, pattern=r"manual_end_game_\d+"),
    CallbackQueryHandler(manage_participants_button, pattern=r"manage_participants_\d+"),
    CallbackQueryHandler(manage_individual_participant_button, pattern=r"manage_participant_\d+_\d+"),
    CallbackQueryHandler(change_participant_role_button, pattern=r"change_role_\d+_\d+_(driver|seeker)"),
    CallbackQueryHandler(mark_participant_found_button, pattern=r"mark_found_\d+_\d+"),
    CallbackQueryHandler(mark_participant_eliminated_button, pattern=r"mark_eliminated_\d+_\d+"),
    CallbackQueryHandler(unmark_participant_found_button, pattern=r"unmark_found_\d+_\d+"),
    CallbackQueryHandler(add_participant_button, pattern=r"add_participant_\d+"),
    CallbackQueryHandler(confirm_add_participant_button, pattern=r"confirm_add_participant_\d+_\d+"),
    CallbackQueryHandler(remove_participant_button, pattern=r"remove_participant_\d+_\d+"),
    CallbackQueryHandler(choose_role_assignment_type_button, pattern=r"choose_role_assignment_type_\d+"),
    CallbackQueryHandler(assign_roles_random_button, pattern=r"assign_roles_random_\d+"),
    CallbackQueryHandler(assign_roles_manual_button, pattern=r"assign_roles_manual_\d+"),
    CallbackQueryHandler(edit_participant_role_button, pattern=r"edit_participant_role_\d+_\d+"),
    CallbackQueryHandler(set_participant_role_button, pattern=r"set_participant_role_\d+_\d+_(driver|seeker|none)"),
    CallbackQueryHandler(auto_fill_roles_button, pattern=r"auto_fill_roles_\d+"),
    CallbackQueryHandler(reset_all_roles_button, pattern=r"reset_all_roles_\d+"),
    CallbackQueryHandler(confirm_manual_roles_button, pattern=r"confirm_manual_roles_\d+"),
    
    # Обработчики информационных callback'ов (без действий)
    CallbackQueryHandler(lambda update, context: update.callback_query.answer(), pattern="separator"),
    CallbackQueryHandler(lambda update, context: update.callback_query.answer("Исправьте ошибки валидации", show_alert=True), pattern="validation_error"),
    CallbackQueryHandler(lambda update, context: update.callback_query.answer("Достигнут лимит этой роли", show_alert=True), pattern="role_limit_reached"),
    
    # Обработчик текстовых сообщений из админ-меню (обновлен для поддержки настроек игры)
    MessageHandler(
        filters.TEXT & 
        filters.Regex(r"^(📋 Список игр|⚙️ Настройки игры|« Назад)$") & 
        ~filters.COMMAND, 
        handle_admin_text
    )
]