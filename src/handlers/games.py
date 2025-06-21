from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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
from telegram.error import BadRequest

from src.services.user_service import UserService
from src.services.game_service import GameService
from src.models.game import GameStatus, GameRole
from src.keyboards.inline import (
    get_game_list_keyboard,
    get_game_actions_keyboard,
    get_admin_game_keyboard,
    get_admin_create_game_keyboard
)
from src.keyboards.reply import get_contextual_main_keyboard

# Состояния для создания игры
CREATE_DISTRICT, CREATE_DATE, CREATE_TIME, CREATE_MAX_PARTICIPANTS, CREATE_DESCRIPTION, CREATE_CONFIRM = range(6)

# Шаблоны для колбэков
GAME_PATTERN = r"game_(\d+)"
GAME_JOIN_PATTERN = r"join_(\d+)"
GAME_LEAVE_PATTERN = r"leave_(\d+)"
GAME_INFO_PATTERN = r"info_(\d+)"
ADMIN_GAME_PATTERN = r"admin_game_(\d+)"
ADMIN_CANCEL_PATTERN = r"cancel_game_(\d+)"
ADMIN_START_PATTERN = r"start_game_(\d+)"
# Новые паттерны для игровых действий
SEND_LOCATION_PATTERN = r"send_location_(\d+)"
SEND_PHOTO_PATTERN = r"send_photo_(\d+)"
FOUND_ME_PATTERN = r"found_me_(\d+)"
FOUND_CAR_PATTERN = r"found_car_(\d+)"
GAME_STATUS_PATTERN = r"game_status_(\d+)"

async def games_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /games - показывает список доступных игр"""
    user_id = update.effective_user.id
    
    # Получаем список предстоящих игр
    upcoming_games = GameService.get_upcoming_games(limit=5)
    
    if not upcoming_games:
        await update.message.reply_text(
            "Сейчас нет запланированных игр. Загляните позже или создайте свою игру!",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        return
    
    # Создаем клавиатуру со списком игр
    keyboard = get_game_list_keyboard(upcoming_games)
    
    await update.message.reply_text(
        "📋 <b>Список доступных игр</b>\n\n"
        "Выберите игру из списка для получения подробной информации и возможности записаться:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def my_games_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /mygames - показывает список игр пользователя"""
    telegram_id = update.effective_user.id
    
    # Получаем пользователя из базы данных по telegram_id
    user, _ = UserService.get_user_by_telegram_id(telegram_id)
    if not user:
        await update.message.reply_text(
            "❌ Ошибка: пользователь не найден в базе данных. Пожалуйста, перезапустите бота командой /start",
            reply_markup=get_contextual_main_keyboard(telegram_id)
        )
        return
    
    # Получаем список игр пользователя, используя правильный user.id
    user_games = GameService.get_user_games(user.id)
    
    if not user_games:
        await update.message.reply_text(
            "Вы еще не записаны ни на одну игру. Используйте /games, чтобы увидеть доступные игры.",
            reply_markup=get_contextual_main_keyboard(telegram_id)
        )
        return
    
    # Создаем клавиатуру со списком игр пользователя
    keyboard = get_game_list_keyboard(user_games)
    
    await update.message.reply_text(
        "🎮 <b>Ваши игры</b>\n\n"
        "Выберите игру из списка для получения подробной информации:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def game_button(update: Update, context: CallbackContext) -> None:
    """Обработчик нажатия на кнопку с игрой"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    logger.info(f"Пользователь {telegram_id} нажал на кнопку игры: {query.data}")
    
    # Извлекаем ID игры из колбэка
    match = re.match(GAME_PATTERN, query.data)
    if not match:
        logger.warning(f"Не удалось извлечь ID игры из callback: {query.data}")
        return
    
    game_id = int(match.group(1))
    logger.info(f"Показываем информацию об игре {game_id} для пользователя {telegram_id}")
    game = GameService.get_game_by_id(game_id)
    
    if not game:
        logger.warning(f"Игра {game_id} не найдена")
        await query.edit_message_text("Игра не найдена или была удалена.")
        return
    
    # Получаем пользователя из базы данных по telegram_id
    user, _ = UserService.get_user_by_telegram_id(telegram_id)
    if not user:
        logger.error(f"Пользователь {telegram_id} не найден в БД")
        await query.edit_message_text(
            "❌ Ошибка: пользователь не найден в базе данных.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_games")
            ]])
        )
        return
    
    # Проверяем, участвует ли пользователь в игре, используя правильный user.id
    is_participant = any(p.user_id == user.id for p in game.participants)
    logger.info(f"Пользователь {telegram_id} {'участвует' if is_participant else 'не участвует'} в игре {game_id}")
    
    # Готовим информацию об игре
    game_info = (
        f"🎮 <b>Информация об игре #{game.id}</b>\n\n"
        f"📍 <b>Район:</b> {game.district}\n"
        f"⏰ <b>Дата и время:</b> {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"👥 <b>Участники:</b> {len(game.participants)}/{game.max_participants}\n"
        f"🚦 <b>Статус:</b> {get_status_text(game.status)}\n"
    )
    
    if game.description:
        game_info += f"\n📝 <b>Описание:</b>\n{game.description}\n"
    
    # Создаем клавиатуру с действиями
    keyboard = get_game_actions_keyboard(game, is_participant)
    logger.info(f"Создана клавиатура для игры {game_id}: {keyboard.inline_keyboard}")
    
    try:
        await query.edit_message_text(
            game_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        logger.info(f"Сообщение успешно обновлено для пользователя {telegram_id}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении сообщения для пользователя {telegram_id}: {e}")
        # Попробуем отправить новое сообщение
        try:
            await query.message.reply_text(
                game_info,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"Отправлено новое сообщение для пользователя {telegram_id}")
        except Exception as e2:
            logger.error(f"Ошибка при отправке нового сообщения: {e2}")

async def join_game_button(update: Update, context: CallbackContext) -> None:
    """Обработчик записи на игру"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    
    # Извлекаем ID игры из колбэка
    match = re.match(GAME_JOIN_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Получаем пользователя из базы данных по telegram_id
    user, _ = UserService.get_user_by_telegram_id(telegram_id)
    if not user:
        await query.edit_message_text(
            "❌ Ошибка: пользователь не найден в базе данных.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_games")
            ]])
        )
        return
    
    # Записываем пользователя на игру, используя правильный user.id
    participant = GameService.join_game(game_id, user.id)
    
    if not participant:
        await query.edit_message_text(
            "❌ Не удалось записаться на игру. Возможно, она уже заполнена или недоступна для записи.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_games")
            ]])
        )
        return
    
    # Получаем обновленную информацию об игре
    game = GameService.get_game_by_id(game_id)
    
    # Готовим информацию об игре
    game_info = (
        f"✅ <b>Вы успешно записались на игру!</b>\n\n"
        f"🎮 <b>Игра #{game.id}</b>\n"
        f"📍 <b>Район:</b> {game.district}\n"
        f"⏰ <b>Дата и время:</b> {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"👥 <b>Участники:</b> {len(game.participants)}/{game.max_participants}\n"
        f"🚦 <b>Статус:</b> {get_status_text(game.status)}\n\n"
        f"Вы получите уведомление перед началом игры. Используйте /mygames для просмотра ваших игр."
    )
    
    await query.edit_message_text(
        game_info,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_games")
        ]]),
        parse_mode="HTML"
    )

async def leave_game_button(update: Update, context: CallbackContext) -> None:
    """Обработчик отмены записи на игру"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    
    # Извлекаем ID игры из колбэка
    match = re.match(GAME_LEAVE_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    
    # Получаем пользователя из базы данных по telegram_id
    user, _ = UserService.get_user_by_telegram_id(telegram_id)
    if not user:
        await query.edit_message_text(
            "❌ Ошибка: пользователь не найден в базе данных.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_games")
            ]])
        )
        return
    
    # Отменяем запись пользователя на игру, используя правильный user.id
    success = GameService.leave_game(game_id, user.id)
    
    if not success:
        await query.edit_message_text(
            "❌ Не удалось отменить запись на игру.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_games")
            ]])
        )
        return
    
    await query.edit_message_text(
        "✅ <b>Вы успешно отменили запись на игру.</b>\n\n"
        "Используйте /games, чтобы посмотреть доступные игры.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_games")
        ]]),
        parse_mode="HTML"
    )

async def back_to_games_button(update: Update, context: CallbackContext) -> None:
    """Обработчик возврата к списку игр"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    logger.info(f"Пользователь {telegram_id} нажал кнопку 'Назад к списку игр'")

    
    
    # Получаем список предстоящих игр
    upcoming_games = GameService.get_upcoming_games(limit=5)
    
    if not upcoming_games:
        logger.info(f"Нет доступных игр для показа пользователю {telegram_id}")
        await query.edit_message_text(
            "Сейчас нет запланированных игр. Загляните позже или создайте свою игру!"
        )
        return
    
    logger.info(f"Показываем {len(upcoming_games)} доступных игр пользователю {telegram_id}")
    # Создаем клавиатуру со списком игр
    keyboard = get_game_list_keyboard(upcoming_games)
    try:
        await query.edit_message_text(
            "📋 <b>Список доступных игр</b>\n\n"
            "Выберите игру из списка для получения подробной информации и возможности записаться:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except BadRequest as err:
        # Telegram always raises this if nothing changed;
        # ignore it and move on
        if "Message is not modified" in err.message:
            return
        # any other BadRequest should bubble up
        raise

async def game_info_button(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки информации об игре (info_{game_id})"""
    query = update.callback_query
    await query.answer("Информация об игре")
    
    telegram_id = query.from_user.id
    logger.info(f"Пользователь {telegram_id} запросил информацию об игре: {query.data}")
    
    # Извлекаем ID игры из колбэка
    match = re.match(GAME_INFO_PATTERN, query.data)
    if not match:
        logger.warning(f"Не удалось извлечь ID игры из info callback: {query.data}")
        return
    
    game_id = int(match.group(1))
    game = GameService.get_game_by_id(game_id)
    
    if not game:
        logger.warning(f"Игра {game_id} не найдена")
        await query.edit_message_text("Игра не найдена или была удалена.")
        return
    
    # Получаем пользователя из базы данных по telegram_id
    user, _ = UserService.get_user_by_telegram_id(telegram_id)
    if not user:
        logger.error(f"Пользователь {telegram_id} не найден в БД")
        await query.edit_message_text(
            "❌ Ошибка: пользователь не найден в базе данных.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад к списку игр", callback_data="back_to_games")
            ]])
        )
        return
    
    is_participant = any(p.user_id == user.id for p in game.participants)
    logger.info(f"Пользователь {telegram_id} {'участвует' if is_participant else 'не участвует'} в игре {game_id}")
    
    # Если игра в процессе и пользователь участвует - показываем игровой интерфейс
    if game.status in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE] and is_participant:
        await show_game_interface(update, context, game, user)
    else:
        # Иначе показываем обычную информацию об игре
        await show_game_info(update, context, game, is_participant)

async def show_game_interface(update: Update, context: CallbackContext, game, user) -> None:
    """Показывает игровой интерфейс для активной игры"""
    query = update.callback_query
    telegram_id = user.telegram_id
    
    # Получаем роль пользователя в игре
    participant = next((p for p in game.participants if p.user_id == user.id), None)
    if not participant:
        await query.edit_message_text("❌ Вы не участвуете в этой игре.")
        return
    
    role = participant.role
    role_text = "🚗 Водитель (прячетесь)" if role == GameRole.DRIVER else "🔍 Искатель (ищете)"
    
    # Формируем игровое сообщение
    game_info = (
        f"🎮 <b>ИГРА В ПРОЦЕССЕ #{game.id}</b>\n\n"
        f"📍 <b>Район:</b> {game.district}\n"
        f"⏰ <b>Начата:</b> {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🎭 <b>Ваша роль:</b> {role_text}\n"
        f"👥 <b>Участники:</b> {len(game.participants)}\n\n"
    )
    
    if role == GameRole.DRIVER:
        game_info += (
            f"🚗 <b>Инструкции для водителя:</b>\n"
            f"• Найдите укромное место для парковки\n"
            f"• Отправьте свою геолокацию\n"
            f"• Ждите, пока вас найдут искатели\n"
            f"• Нажмите 'Меня нашли' когда вас обнаружат\n\n"
        )
    else:
        game_info += (
            f"🔍 <b>Инструкции для искателя:</b>\n"
            f"• Ищите спрятавшегося водителя\n"
            f"• Используйте подсказки и логику\n"
            f"• Отправляйте фото когда найдете\n"
            f"• Нажмите 'Нашел водителя' при обнаружении\n\n"
        )
    
    # Создаем игровую клавиатуру
    if role == GameRole.DRIVER:
        buttons = [
            [InlineKeyboardButton("📍 Отправить геолокацию", callback_data=f"send_location_{game.id}")],
            [InlineKeyboardButton("📸 Фото места", callback_data=f"photo_place_{game.id}")],
            [InlineKeyboardButton("🚗 Меня нашли!", callback_data=f"found_seeker_{game.id}")],
            [InlineKeyboardButton("📊 Статус игры", callback_data=f"game_status_{game.id}"),
             InlineKeyboardButton("❓ Помощь", callback_data=f"game_help_{game.id}")],
            [InlineKeyboardButton("◀️ Назад к списку", callback_data="back_to_games")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("📍 Моя позиция", callback_data=f"send_location_{game.id}")],
            [InlineKeyboardButton("📸 Фото находки", callback_data=f"photo_find_{game.id}")],
            [InlineKeyboardButton("🔍 Нашел водителя!", callback_data=f"found_driver_{game.id}")],
            [InlineKeyboardButton("📊 Статус игры", callback_data=f"game_status_{game.id}"),
             InlineKeyboardButton("❓ Помощь", callback_data=f"game_help_{game.id}")],
            [InlineKeyboardButton("◀️ Назад к списку", callback_data="back_to_games")]
        ]
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    try:
        await query.edit_message_text(
            game_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        logger.info(f"Показан игровой интерфейс для пользователя {telegram_id} в игре {game.id}")
    except Exception as e:
        logger.error(f"Ошибка при показе игрового интерфейса: {e}")

async def show_game_info(update: Update, context: CallbackContext, game, is_participant) -> None:
    """Показывает обычную информацию об игре"""
    query = update.callback_query
    
    # Готовим информацию об игре
    game_info = (
        f"🎮 <b>Информация об игре #{game.id}</b>\n\n"
        f"📍 <b>Район:</b> {game.district}\n"
        f"⏰ <b>Дата и время:</b> {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"👥 <b>Участники:</b> {len(game.participants)}/{game.max_participants}\n"
        f"🚦 <b>Статус:</b> {get_status_text(game.status)}\n"
    )
    
    if game.description:
        game_info += f"\n📝 <b>Описание:</b>\n{game.description}\n"
    
    # Создаем клавиатуру с действиями
    keyboard = get_game_actions_keyboard(game, is_participant)
    
    try:
        await query.edit_message_text(
            game_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        logger.info(f"Показана информация об игре {game.id}")
    except BadRequest as err:
        # Telegram always raises this if nothing changed;
        # ignore it and move on
        if "Message is not modified" in err.message:
            return
        # any other BadRequest should bubble up
        raise

# Функция для получения текстового представления статуса
def get_status_text(status: GameStatus) -> str:
    """Возвращает текстовое представление статуса игры"""
    status_texts = {
        GameStatus.RECRUITING: "📝 Набор участников",
        GameStatus.UPCOMING: "⏰ Скоро начнется",
        GameStatus.HIDING_PHASE: "🏃 Фаза пряток",
        GameStatus.SEARCHING_PHASE: "🔍 Фаза поиска",
        GameStatus.COMPLETED: "✅ Завершена",
        GameStatus.CANCELED: "❌ Отменена"
    }
    return status_texts.get(status, str(status))

# Регистрация обработчиков для игр
game_handlers = [
    CommandHandler("games", games_command),
    CommandHandler("mygames", my_games_command),
    CallbackQueryHandler(game_button, pattern=GAME_PATTERN),
    CallbackQueryHandler(game_info_button, pattern=GAME_INFO_PATTERN),
    CallbackQueryHandler(join_game_button, pattern=GAME_JOIN_PATTERN),
    CallbackQueryHandler(leave_game_button, pattern=GAME_LEAVE_PATTERN),
    CallbackQueryHandler(back_to_games_button, pattern="back_to_games")
] 