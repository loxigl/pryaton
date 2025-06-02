from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.models.game import GameStatus

def get_game_list_keyboard(games):
    """Инлайн-клавиатура для списка игр"""
    buttons = []
    for game in games:
        # Формат: "Район, дата (участники/максимум)"
        game_info = f"{game.district}, {game.scheduled_at.strftime('%d.%m %H:%M')} ({len(game.participants)}/{game.max_participants})"
        buttons.append([InlineKeyboardButton(text=game_info, callback_data=f"game_{game.id}")])
    
    # Добавляем кнопку "Обновить"
    buttons.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_games")])
    
    return InlineKeyboardMarkup(buttons)

def get_game_actions_keyboard(game, is_participant=False):
    """Инлайн-клавиатура для действий с игрой"""
    buttons = []
    
    # Проверяем статус игры и участие пользователя
    if game.status == GameStatus.RECRUITING:
        if is_participant:
            buttons.append([InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"leave_{game.id}")])
        else:
            buttons.append([InlineKeyboardButton(text="✅ Записаться", callback_data=f"join_{game.id}")])
    elif game.status == GameStatus.UPCOMING:
        if is_participant:
            buttons.append([InlineKeyboardButton(text="✅ Вы записаны", callback_data=f"info_{game.id}")])
            buttons.append([InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"leave_{game.id}")])
        else:
            # Игра скоро начнется, запись может быть закрыта
            buttons.append([InlineKeyboardButton(text="⏰ Скоро начнется", callback_data=f"info_{game.id}")])
    elif game.status == GameStatus.IN_PROGRESS:
        if is_participant:
            buttons.append([InlineKeyboardButton(text="🎮 Игра в процессе", callback_data=f"info_{game.id}")])
            buttons.append([InlineKeyboardButton(text="📍 Отправить геолокацию", callback_data=f"send_location_{game.id}")])
        else:
            buttons.append([InlineKeyboardButton(text="▶️ Идет игра", callback_data=f"info_{game.id}")])
    elif game.status == GameStatus.COMPLETED:
        buttons.append([InlineKeyboardButton(text="✅ Игра завершена", callback_data=f"info_{game.id}")])
    elif game.status == GameStatus.CANCELED:
        buttons.append([InlineKeyboardButton(text="❌ Игра отменена", callback_data=f"info_{game.id}")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_games")])
    
    return InlineKeyboardMarkup(buttons)

def get_admin_game_keyboard(game):
    """Инлайн-клавиатура для управления игрой (админ)"""
    buttons = []
    
    # Добавляем кнопки в зависимости от статуса игры
    if game.status == GameStatus.RECRUITING or game.status == GameStatus.UPCOMING:
        buttons.append([InlineKeyboardButton(text="🎲 Распределить роли", callback_data=f"assign_roles_{game.id}")])
        # Добавляем кнопку редактирования для игр, которые можно редактировать
        buttons.append([InlineKeyboardButton(text="✏️ Редактировать игру", callback_data=f"edit_game_{game.id}")])
    
    if game.status == GameStatus.RECRUITING:
        # Для игр в статусе набора можно сделать досрочный запуск
        buttons.append([InlineKeyboardButton(text="⚡ Запустить досрочно", callback_data=f"start_early_{game.id}")])
    
    if game.status == GameStatus.UPCOMING:
        buttons.append([InlineKeyboardButton(text="▶️ Начать игру", callback_data=f"start_game_{game.id}")])
    
    if game.status == GameStatus.IN_PROGRESS:
        buttons.append([InlineKeyboardButton(text="⏹ Завершить игру", callback_data=f"end_game_{game.id}")])
    
    # Кнопка отмены доступна для любой игры, которая не завершена и не отменена
    if game.status != GameStatus.COMPLETED and game.status != GameStatus.CANCELED:
        buttons.append([InlineKeyboardButton(text="❌ Отменить игру", callback_data=f"cancel_game_{game.id}")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_admin_games")])
    
    return InlineKeyboardMarkup(buttons)

def get_admin_create_game_keyboard():
    """Инлайн-клавиатура для создания игры (админ)"""
    buttons = [
        [InlineKeyboardButton(text="➕ Создать новую игру", callback_data="create_game")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_admin_games")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_location_keyboard(game_id):
    """Инлайн-клавиатура для отправки геолокации"""
    buttons = [
        [InlineKeyboardButton(text="📍 Отправить текущую локацию", callback_data=f"send_location_{game_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_location")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_game_finish_keyboard(game_id, is_driver=False):
    """Инлайн-клавиатура для завершения игры"""
    if is_driver:
        text = "🚗 Меня нашли"
    else:
        text = "🔍 Я нашел машину"
    
    buttons = [
        [InlineKeyboardButton(text=text, callback_data=f"finish_game_{game_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_finish")]
    ]
    return InlineKeyboardMarkup(buttons)
 