from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler, 
    CallbackContext, 
    ConversationHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters
)
from datetime import datetime
import re
from loguru import logger

from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.settings_service import SettingsService
from src.models.game import GameStatus, GameRole
from src.keyboards.inline import get_admin_game_keyboard
from src.keyboards.reply import get_district_keyboard, get_contextual_main_keyboard

# Состояния для создания игры
CREATE_DISTRICT, CREATE_DATE, CREATE_TIME, CREATE_MAX_PARTICIPANTS, CREATE_MAX_DRIVERS, CREATE_DESCRIPTION, CREATE_CONFIRM = range(7)

# Состояния для редактирования правил
EDIT_RULES = 10

# Состояния для редактирования районов
DISTRICT_ACTION, ADD_DISTRICT_NAME, REMOVE_DISTRICT_NAME = range(11, 14)

# Состояния для редактирования ролей
ROLE_ACTION, ADD_ROLE_NAME, REMOVE_ROLE_NAME = range(14, 17)

# Состояния для редактирования игр
EDIT_GAME_FIELD, EDIT_GAME_VALUE, EDIT_GAME_SAVE = range(17, 20)

# Состояния для inline редактирования
EDIT_GAME_DISTRICT_VALUE, EDIT_GAME_DATETIME_VALUE, EDIT_GAME_PARTICIPANTS_VALUE, EDIT_GAME_DRIVERS_VALUE, EDIT_GAME_DESCRIPTION_VALUE = range(20, 25)

# Шаблоны для колбэков
ADMIN_GAME_PATTERN = r"admin_game_(\d+)"
ADMIN_CANCEL_PATTERN = r"cancel_game_(\d+)"
ADMIN_START_PATTERN = r"start_game_(\d+)"
ADMIN_ASSIGN_ROLES_PATTERN = r"assign_roles_(\d+)"
ADMIN_EDIT_GAME_PATTERN = r"edit_game_(\d+)"
EDIT_DISTRICT_PATTERN = r"edit_district_(\d+)"
EDIT_DATETIME_PATTERN = r"edit_datetime_(\d+)"
EDIT_PARTICIPANTS_PATTERN = r"edit_participants_(\d+)"
EDIT_DRIVERS_PATTERN = r"edit_drivers_(\d+)"
EDIT_DESCRIPTION_PATTERN = r"edit_description_(\d+)"
SET_DISTRICT_PATTERN = r"set_district_(\d+)_(.+)"
SET_PARTICIPANTS_PATTERN = r"set_participants_(\d+)_(\d+)"
SET_DRIVERS_PATTERN = r"set_drivers_(\d+)_(\d+)"

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Получение админской клавиатуры"""
    return ReplyKeyboardMarkup([
        ["🎮 Создать игру", "📋 Список игр"],
        ["👥 Управление пользователями", "📊 Мониторинг"],
        ["📅 События планировщика", "🏙️ Управление районами"],
        ["🗺 Управление зонами", "👤 Управление ролями"],
        ["📋 Редактировать правила", "🏠 Главное меню"]
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
        return get_contextual_main_keyboard(is_admin)

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
    all_games = GameService.get_upcoming_games(limit=10)
    
    if not all_games:
        await update.message.reply_text(
            "Сейчас нет запланированных игр.",
            reply_markup=get_admin_or_main_keyboard(user_id, True)
        )
        return
    
    # Создаем клавиатуру для админа
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{game.district} - {game.scheduled_at.strftime('%d.%m %H:%M')} ({len(game.participants)}/{game.max_participants})",
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

async def assign_roles_button(update: Update, context: CallbackContext) -> None:
    """Обработчик распределения ролей администратором"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Извлекаем ID игры из колбэка
    match = re.match(ADMIN_ASSIGN_ROLES_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Распределяем роли
    roles = GameService.assign_roles(game_id)
    
    if not roles:
        await query.edit_message_text(
            "❌ Не удалось распределить роли. Возможно, в игре нет участников.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")
            ]])
        )
        return
    
    # Формируем сообщение с распределением ролей
    game = GameService.get_game_by_id(game_id)
    roles_info = "\n".join([
        f"- {p.user.name}: {'🚗 Водитель' if p.role == GameRole.DRIVER else '🔍 Искатель'}" 
        for p in game.participants if p.role
    ])
    
    await query.edit_message_text(
        f"✅ <b>Роли успешно распределены!</b>\n\n"
        f"<b>Результаты распределения:</b>\n{roles_info}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Назад к управлению игрой", callback_data=f"admin_game_{game_id}")
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
    """Обработчик кнопки изменения даты и времени"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    match = re.match(EDIT_DATETIME_PATTERN, query.data)
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
    
    await query.edit_message_text(
        f"⏰ <b>Изменение даты и времени для игры #{game_id}</b>\n\n"
        f"Текущие дата и время: <b>{game.scheduled_at.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
        f"Напишите новую дату и время в формате:\n"
        f"<code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n\n"
        f"Например: <code>25.12.2024 18:30</code>",
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
    all_games = GameService.get_upcoming_games(limit=10)
    
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
        "Шаг 1/7: Выберите район проведения игры:",
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
        "Шаг 2/7: Введите дату проведения игры в формате ДД.ММ.ГГГГ (например, 15.06.2025):",
        
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
        "Шаг 3/7: Введите время проведения игры в формате ЧЧ:ММ (например, 18:30):"
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
        "Шаг 4/7: Введите максимальное количество участников (от 3 до 20):"
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
        f"Шаг 5/7: Введите количество водителей (прячущихся) от 1 до {max_participants - 1}:"
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
        f"Шаг 6/7: Введите описание игры (или отправьте '-' для пропуска):"
    )
    
    return CREATE_DESCRIPTION

async def process_description(update: Update, context: CallbackContext) -> int:
    """Обработка ввода описания"""
    description = update.message.text
    
    if description == "-":
        description = None
    
    context.user_data["description"] = description
    
    # Собираем всю информацию для подтверждения
    district = context.user_data["game_district"]
    game_datetime = context.user_data["game_datetime"]
    max_participants = context.user_data["max_participants"]
    max_drivers = context.user_data["max_drivers"]
    max_seekers = max_participants - max_drivers
    
    confirmation_text = (
        "📋 <b>Подтверждение создания игры</b>\n\n"
        f"📍 <b>Район:</b> {district}\n"
        f"⏰ <b>Дата и время:</b> {game_datetime.strftime('%d.%m.%Y %H:%M')}\n"
        f"👥 <b>Максимум участников:</b> {max_participants}\n"
        f"🚗 <b>Водители:</b> {max_drivers}\n"
        f"🔍 <b>Искатели:</b> {max_seekers}\n"
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
        
        max_seekers = max_participants - max_drivers
        await update.message.reply_text(
            f"✅ <b>Игра успешно создана!</b>\n\n"
            f"ID игры: {game.id}\n"
            f"Район: {game.district}\n"
            f"Дата и время: {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"Участников: {game.max_participants} (🚗 {game.max_drivers} водителей, 🔍 {max_seekers} искателей)\n\n"
            f"Используйте /admingames для управления играми.",
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
    
    roles = SettingsService.get_all_roles()
    active_roles = [r for r in roles if r.is_active]
    inactive_roles = [r for r in roles if not r.is_active]
    
    active_text = "\n".join([f"• {role.name}" for role in active_roles])
    inactive_text = "\n".join([f"• {role.name}" for role in inactive_roles]) if inactive_roles else "Нет"
    
    keyboard = ReplyKeyboardMarkup([
        ["➕ Добавить роль", "❌ Удалить роль"],
        ["🔄 Восстановить роль", "📋 Показать все"],
        ["« Назад в админку"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        f"👤 <b>Управление ролями</b>\n\n"
        f"<b>Активные роли:</b>\n{active_text}\n\n"
        f"<b>Деактивированные:</b>\n{inactive_text}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ROLE_ACTION

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

# Обработчики для ролей (аналогично районам)
async def role_action_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик действий с ролями"""
    text = update.message.text
    
    if text == "➕ Добавить роль":
        await update.message.reply_text(
            "Введите название новой роли:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_ROLE_NAME
    elif text == "❌ Удалить роль":
        roles = SettingsService.get_available_roles()
        if not roles:
            await update.message.reply_text(
                "Нет активных ролей для удаления.",
                reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
            )
            return ConversationHandler.END
        
        keyboard = ReplyKeyboardMarkup(
            [[role] for role in roles] + [["« Отмена"]],
            resize_keyboard=True
        )
        await update.message.reply_text(
            "Выберите роль для деактивации:",
            reply_markup=keyboard
        )
        return REMOVE_ROLE_NAME
    elif text == "🔄 Восстановить роль":
        all_roles = SettingsService.get_all_roles()
        inactive_roles = [r.name for r in all_roles if not r.is_active]
        
        if not inactive_roles:
            await update.message.reply_text(
                "Нет деактивированных ролей для восстановления.",
                reply_markup=get_admin_or_main_keyboard(update.effective_user.id, True)
            )
            return ConversationHandler.END
        
        keyboard = ReplyKeyboardMarkup(
            [[role] for role in inactive_roles] + [["« Отмена"]],
            resize_keyboard=True
        )
        await update.message.reply_text(
            "Выберите роль для восстановления:",
            reply_markup=keyboard
        )
        context.user_data["restore_role"] = True
        return REMOVE_ROLE_NAME
    elif text == "« Назад в админку":
        return await admin_command(update, context)
    
    return ROLE_ACTION

async def add_role_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик добавления новой роли"""
    role_name = update.message.text.strip()
    
    if len(role_name) < 2:
        await update.message.reply_text(
            "Название роли должно содержать минимум 2 символа. Попробуйте еще раз:"
        )
        return ADD_ROLE_NAME
    
    success = SettingsService.add_role(role_name)
    
    if success:
        await update.message.reply_text(
            f"✅ Роль '{role_name}' успешно добавлена!"
        )
    else:
        await update.message.reply_text(
            f"❌ Роль '{role_name}' уже существует или произошла ошибка."
        )
    
    # Возвращаемся к экрану управления ролями
    return await manage_roles_command(update, context)

async def remove_role_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик удаления/восстановления роли"""
    role_name = update.message.text.strip()
    
    if role_name == "« Отмена":
        # Возвращаемся к управлению ролями
        return await manage_roles_command(update, context)
    
    restore_mode = context.user_data.get("restore_role", False)
    
    if restore_mode:
        # Восстанавливаем роль
        success = SettingsService.add_role(role_name)  # Функция сама проверит и восстановит
        action = "восстановлена"
    else:
        # Деактивируем роль
        success = SettingsService.remove_role(role_name)
        action = "деактивирована"
    
    if success:
        await update.message.reply_text(
            f"✅ Роль '{role_name}' успешно {action}!"
        )
    else:
        await update.message.reply_text(
            f"❌ Не удалось обработать роль '{role_name}'."
        )
    
    # Очищаем флаг восстановления
    if "restore_role" in context.user_data:
        del context.user_data["restore_role"]
    
    # Возвращаемся к экрану управления ролями
    return await manage_roles_command(update, context)

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
        ADD_ROLE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_role_handler)],
        REMOVE_ROLE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_role_handler)]
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


# Регистрация обработчиков для админ-функций
admin_handlers = [
    CommandHandler("admin", admin_command),
    CommandHandler("admingames", admin_games_command),
    CallbackQueryHandler(admin_game_button, pattern=ADMIN_GAME_PATTERN),
    CallbackQueryHandler(cancel_game_button, pattern=ADMIN_CANCEL_PATTERN),
    CallbackQueryHandler(start_game_button, pattern=ADMIN_START_PATTERN),
    CallbackQueryHandler(start_game_early_button, pattern=r"start_early_\d+"),
    CallbackQueryHandler(assign_roles_button, pattern=ADMIN_ASSIGN_ROLES_PATTERN),
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
    # Обработчик текстовых сообщений из админ-меню (только для команд, не являющихся ConversationHandler)
    MessageHandler(
        filters.TEXT & 
        filters.Regex(r"^(📋 Список игр|« Назад)$") & 
        ~filters.COMMAND, 
        handle_admin_text
    )
]