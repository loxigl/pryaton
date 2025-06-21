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
    elif game.status in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
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
        buttons.append([InlineKeyboardButton(text="🎲 Распределить роли", callback_data=f"choose_role_assignment_type_{game.id}")])
        # Добавляем кнопку редактирования для игр, которые можно редактировать
        buttons.append([InlineKeyboardButton(text="✏️ Редактировать игру", callback_data=f"edit_game_{game.id}")])
    
    # Добавляем кнопку ручного управления для всех активных игр
    if game.status not in [GameStatus.COMPLETED, GameStatus.CANCELED]:
        buttons.append([InlineKeyboardButton(text="🎮 Ручное управление", callback_data=f"manual_control_{game.id}")])
    
    if game.status == GameStatus.RECRUITING:
        # Для игр в статусе набора можно сделать досрочный запуск
        buttons.append([InlineKeyboardButton(text="⚡ Запустить досрочно", callback_data=f"start_early_{game.id}")])
    
    if game.status == GameStatus.UPCOMING:
        buttons.append([InlineKeyboardButton(text="▶️ Начать игру", callback_data=f"start_game_{game.id}")])
    
    if game.status in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
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

def get_game_settings_keyboard(settings):
    """Инлайн-клавиатура для настроек игры"""
    buttons = []
    
    # Режим управления
    mode_icon = "🔴" if settings.manual_control_mode else "🟢"
    mode_text = "Ручной" if settings.manual_control_mode else "Автоматический"
    buttons.append([InlineKeyboardButton(
        text=f"{mode_icon} Режим управления: {mode_text}",
        callback_data="toggle_manual_control"
    )])
    
    # Настройки автоматизации (только если не ручной режим)
    if not settings.manual_control_mode:
        buttons.append([InlineKeyboardButton(
            text="⚙️ Настройки автоматизации",
            callback_data="automation_settings"
        )])
    
    # Временные настройки
    buttons.append([InlineKeyboardButton(
        text="⏱ Временные настройки",
        callback_data="time_settings"
    )])
    
    # Настройки уведомлений
    buttons.append([InlineKeyboardButton(
        text="🔔 Настройки уведомлений",
        callback_data="notification_settings"
    )])
    
    # Сброс к умолчанию
    buttons.append([InlineKeyboardButton(
        text="🔄 Сбросить к умолчанию",
        callback_data="reset_settings"
    )])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_admin")])
    
    return InlineKeyboardMarkup(buttons)

def get_automation_settings_keyboard(settings):
    """Клавиатура для настроек автоматизации"""
    buttons = []
    
    # Автостарт игры
    auto_start_icon = "✅" if settings.auto_start_game else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{auto_start_icon} Автостарт игры",
        callback_data="toggle_auto_start_game"
    )])
    
    # Автораспределение ролей
    auto_roles_icon = "✅" if settings.auto_assign_roles else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{auto_roles_icon} Автораспределение ролей",
        callback_data="toggle_auto_assign_roles"
    )])
    
    # Автостарт фазы пряток
    auto_hiding_icon = "✅" if settings.auto_start_hiding else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{auto_hiding_icon} Автостарт фазы пряток",
        callback_data="toggle_auto_start_hiding"
    )])
    
    # Автостарт фазы поиска
    auto_searching_icon = "✅" if settings.auto_start_searching else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{auto_searching_icon} Автостарт фазы поиска",
        callback_data="toggle_auto_start_searching"
    )])
    
    # Автозавершение игры
    auto_end_icon = "✅" if settings.auto_end_game else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{auto_end_icon} Автозавершение игры",
        callback_data="toggle_auto_end_game"
    )])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="game_settings")])
    
    return InlineKeyboardMarkup(buttons)

def get_time_settings_keyboard(settings):
    """Клавиатура для временных настроек"""
    buttons = []
    
    # Длительность фазы пряток
    buttons.append([InlineKeyboardButton(
        text=f"🕐 Фаза пряток: {settings.hiding_phase_duration} мин",
        callback_data="set_hiding_duration"
    )])
    
    # Длительность фазы поиска
    buttons.append([InlineKeyboardButton(
        text=f"🕑 Фаза поиска: {settings.searching_phase_duration} мин",
        callback_data="set_searching_duration"
    )])
    
    # Время уведомления о старте
    buttons.append([InlineKeyboardButton(
        text=f"🔔 Уведомление о старте: {settings.game_start_notification_time} мин",
        callback_data="set_notification_time"
    )])
    
    # Минимум участников для старта
    buttons.append([InlineKeyboardButton(
        text=f"👥 Мин. участников: {settings.min_participants_to_start}",
        callback_data="set_min_participants"
    )])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="game_settings")])
    
    return InlineKeyboardMarkup(buttons)

def get_notification_settings_keyboard(settings):
    """Клавиатура для настроек уведомлений"""
    buttons = []
    
    # Уведомления о назначении ролей
    notify_role_icon = "✅" if settings.notify_on_role_assignment else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{notify_role_icon} Уведомления о ролях",
        callback_data="toggle_notify_role"
    )])
    
    # Уведомления о смене фаз
    notify_phase_icon = "✅" if settings.notify_on_phase_change else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{notify_phase_icon} Уведомления о фазах",
        callback_data="toggle_notify_phase"
    )])
    
    # Уведомления о действиях участников
    notify_action_icon = "✅" if settings.notify_on_participant_action else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{notify_action_icon} Уведомления о действиях",
        callback_data="toggle_notify_action"
    )])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="game_settings")])
    
    return InlineKeyboardMarkup(buttons)

def get_manual_control_keyboard(game_id, game_status, participants_info):
    """Клавиатура для ручного управления игрой"""
    buttons = []
    
    # Кнопки в зависимости от статуса игры
    if game_status == GameStatus.UPCOMING.value:
        buttons.append([InlineKeyboardButton(
            text="🎲 Распределить роли",
            callback_data=f"choose_role_assignment_type_{game_id}"
        )])
        buttons.append([InlineKeyboardButton(
            text="▶️ Начать фазу пряток",
            callback_data=f"manual_start_hiding_{game_id}"
        )])
    
    elif game_status == GameStatus.HIDING_PHASE.value:
        buttons.append([InlineKeyboardButton(
            text="🔍 Начать фазу поиска",
            callback_data=f"manual_start_searching_{game_id}"
        )])
        buttons.append([InlineKeyboardButton(
            text="👥 Управление участниками",
            callback_data=f"manage_participants_{game_id}"
        )])
    
    elif game_status == GameStatus.SEARCHING_PHASE.value:
        buttons.append([InlineKeyboardButton(
            text="👥 Управление участниками",
            callback_data=f"manage_participants_{game_id}"
        )])
    
    # Общие кнопки для активных игр
    if game_status not in [GameStatus.COMPLETED.value, GameStatus.CANCELED.value]:
        buttons.append([InlineKeyboardButton(
            text="⏹ Завершить игру",
            callback_data=f"manual_end_game_{game_id}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data=f"manual_control_{game_id}"
    )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к игре",
        callback_data=f"admin_game_{game_id}"
    )])
    
    return InlineKeyboardMarkup(buttons)

def get_participants_management_keyboard(game_id, participants):
    """Клавиатура для управления участниками"""
    buttons = []
    
    # Добавляем кнопки для каждого участника
    for participant in participants:
        role_emoji = "🚗" if participant.get("role") == "driver" else "🔍"
        status_emoji = "✅" if participant.get("is_found") else "⏳"
        
        button_text = f"{role_emoji}{status_emoji} {participant['user_name']}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"manage_participant_{game_id}_{participant['id']}"
        )])
    
    # Добавляем кнопку для добавления нового участника
    buttons.append([InlineKeyboardButton(
        text="➕ Добавить участника",
        callback_data=f"add_participant_{game_id}"
    )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к управлению",
        callback_data=f"manual_control_{game_id}"
    )])
    
    return InlineKeyboardMarkup(buttons)

def get_participant_actions_keyboard(game_id, participant_id, participant_info):
    """Клавиатура для действий с конкретным участником"""
    buttons = []
    
    # Изменение роли (только если игра не началась)
    if participant_info.get("role"):
        current_role = participant_info["role"]
        new_role = "seeker" if current_role == "driver" else "driver"
        new_role_emoji = "🔍" if new_role == "seeker" else "🚗"
        
        buttons.append([InlineKeyboardButton(
            text=f"🔄 Сделать {new_role_emoji}",
            callback_data=f"change_role_{game_id}_{participant_id}_{new_role}"
        )])
    
    # Отметить как найденного/выбывшего
    if not participant_info.get("is_found"):
        buttons.append([InlineKeyboardButton(
            text="✅ Отметить найденным",
            callback_data=f"mark_found_{game_id}_{participant_id}"
        )])
        buttons.append([InlineKeyboardButton(
            text="❌ Отметить выбывшим",
            callback_data=f"mark_eliminated_{game_id}_{participant_id}"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="🔄 Отменить нахождение",
            callback_data=f"unmark_found_{game_id}_{participant_id}"
        )])
    
    # Кнопка удаления участника
    buttons.append([InlineKeyboardButton(
        text="🗑 Удалить участника",
        callback_data=f"remove_participant_{game_id}_{participant_id}"
    )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к участникам",
        callback_data=f"manage_participants_{game_id}"
    )])
    
    return InlineKeyboardMarkup(buttons)

def get_profile_main_keyboard():
    """Основная inline клавиатура для профиля"""
    buttons = [
        [InlineKeyboardButton(text="✏️ Редактировать профиль", callback_data="edit_profile")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_profile_edit_keyboard():
    """Inline клавиатура для редактирования профиля"""
    buttons = [
        [InlineKeyboardButton(text="👤 Редактировать имя", callback_data="edit_profile_name")],
        [InlineKeyboardButton(text="📱 Редактировать телефон", callback_data="edit_profile_phone")],
        [InlineKeyboardButton(text="🏘 Редактировать район", callback_data="edit_profile_district")],
        [InlineKeyboardButton(text="🎭 Редактировать роль", callback_data="edit_profile_role")],
        [InlineKeyboardButton(text="🚗 Марка автомобиля", callback_data="edit_profile_car_brand")],
        [InlineKeyboardButton(text="🎨 Цвет автомобиля", callback_data="edit_profile_car_color")],
        [InlineKeyboardButton(text="🔢 Гос. номер", callback_data="edit_profile_car_number")],
        [InlineKeyboardButton(text="◀️ Назад к профилю", callback_data="back_to_profile")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_profile_field_confirm_keyboard(field):
    """Клавиатура подтверждения изменения поля профиля"""
    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_profile_{field}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_profile_edit")],
        [InlineKeyboardButton(text="◀️ К редактированию", callback_data="edit_profile")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_profile_back_keyboard():
    """Клавиатура для возврата к профилю"""
    buttons = [
        [InlineKeyboardButton(text="◀️ Назад к профилю", callback_data="back_to_profile")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_role_selection_keyboard():
    """Inline клавиатура для выбора роли"""
    from src.services.settings_service import SettingsService
    available_roles = SettingsService.get_available_roles()
    
    buttons = []
    for role in available_roles:
        buttons.append([InlineKeyboardButton(text=role, callback_data=f"select_role_{role}")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад к редактированию", callback_data="edit_profile")])
    return InlineKeyboardMarkup(buttons)

def get_district_selection_keyboard():
    """Inline клавиатура для выбора района"""
    from src.services.settings_service import SettingsService
    available_districts = SettingsService.get_districts()
    
    buttons = []
    for district in available_districts:
        buttons.append([InlineKeyboardButton(text=district, callback_data=f"select_district_{district}")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад к редактированию", callback_data="edit_profile")])
    return InlineKeyboardMarkup(buttons)

def get_role_assignment_type_keyboard(game_id):
    """Клавиатура для выбора типа распределения ролей"""
    buttons = [
        [InlineKeyboardButton(
            text="🎲 Случайное распределение",
            callback_data=f"assign_roles_random_{game_id}"
        )],
        [InlineKeyboardButton(
            text="✋ Ручное распределение",
            callback_data=f"assign_roles_manual_{game_id}"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к управлению",
            callback_data=f"manual_control_{game_id}"
        )]
    ]
    return InlineKeyboardMarkup(buttons)

def get_manual_role_assignment_keyboard(game_id, participants, max_drivers):
    """Новая улучшенная клавиатура для ручного назначения ролей участникам"""
    buttons = []
    
    # Подсчитываем текущие роли
    drivers = [p for p in participants if p.get("current_role") == "driver"]
    seekers = [p for p in participants if p.get("current_role") == "seeker"]
    unassigned = [p for p in participants if not p.get("current_role")]
    
    # Заголовок с текущим состоянием
    status_text = f"👥 Участников: {len(participants)} | 🚗 Водители: {len(drivers)}/{max_drivers} | 🔍 Искатели: {len(seekers)}"
    
    # Список всех участников с их текущими ролями
    for participant in participants:
        user_name = participant['user_name']
        current_role = participant.get('current_role')
        
        if current_role == "driver":
            role_emoji = "🚗"
            role_text = "Водитель"
        elif current_role == "seeker":
            role_emoji = "🔍"
            role_text = "Искатель"
        else:
            role_emoji = "❓"
            role_text = "Не назначена"
        
        button_text = f"{role_emoji} {user_name} - {role_text}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"edit_participant_role_{game_id}_{participant['id']}"
        )])
    
    # Разделитель
    buttons.append([InlineKeyboardButton(text="─" * 30, callback_data="separator")])
    
    # Кнопки быстрых действий
    quick_actions = []
    
    # Автозаполнение - назначить роли автоматически оставшимся
    if unassigned:
        quick_actions.append(InlineKeyboardButton(
            text="⚡ Автозаполнение",
            callback_data=f"auto_fill_roles_{game_id}"
        ))
    
    # Сброс всех ролей
    if drivers or seekers:
        quick_actions.append(InlineKeyboardButton(
            text="🔄 Сбросить все",
            callback_data=f"reset_all_roles_{game_id}"
        ))
    
    if quick_actions:
        # Разбиваем кнопки быстрых действий по 2 в ряд
        for i in range(0, len(quick_actions), 2):
            buttons.append(quick_actions[i:i+2])
    
    # Кнопка подтверждения (доступна только если все роли назначены корректно)
    can_confirm = (
        len(unassigned) == 0 and 
        len(drivers) > 0 and len(drivers) <= max_drivers and 
        len(seekers) > 0
    )
    
    if can_confirm:
        buttons.append([InlineKeyboardButton(
            text="✅ Подтвердить распределение",
            callback_data=f"confirm_manual_roles_{game_id}"
        )])
    else:
        # Показываем что нужно исправить
        error_text = "❌ "
        if len(unassigned) > 0:
            error_text += f"Назначьте роли всем ({len(unassigned)} осталось)"
        elif len(drivers) == 0:
            error_text += "Нужен хотя бы 1 водитель"
        elif len(drivers) > max_drivers:
            error_text += f"Слишком много водителей ({len(drivers)}/{max_drivers})"
        elif len(seekers) == 0:
            error_text += "Нужен хотя бы 1 искатель"
        
        buttons.append([InlineKeyboardButton(
            text=error_text,
            callback_data="validation_error"
        )])
    
    # Кнопка возврата
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к выбору типа",
        callback_data=f"choose_role_assignment_type_{game_id}"
    )])
    
    return InlineKeyboardMarkup(buttons)

def get_participant_role_edit_keyboard(game_id, participant_id, participant_name, current_role, max_drivers, current_driver_count):
    """Клавиатура для редактирования роли конкретного участника"""
    buttons = []
    
    # Заголовок с именем участника
    current_role_text = "Не назначена"
    if current_role == "driver":
        current_role_text = "🚗 Водитель"
    elif current_role == "seeker":
        current_role_text = "🔍 Искатель"
    
    # Кнопки выбора роли
    role_buttons = []
    
    # Кнопка "Водитель"
    can_be_driver = (current_role == "driver") or (current_driver_count < max_drivers)
    if can_be_driver:
        driver_text = "🚗 Назначить водителем"
        if current_role == "driver":
            driver_text = "🚗 Водитель (текущая)"
        
        role_buttons.append(InlineKeyboardButton(
            text=driver_text,
            callback_data=f"set_participant_role_{game_id}_{participant_id}_driver"
        ))
    else:
        role_buttons.append(InlineKeyboardButton(
            text=f"🚗 Водитель ({current_driver_count}/{max_drivers})",
            callback_data="role_limit_reached"
        ))
    
    # Кнопка "Искатель"
    seeker_text = "🔍 Назначить искателем"
    if current_role == "seeker":
        seeker_text = "🔍 Искатель (текущая)"
    
    role_buttons.append(InlineKeyboardButton(
        text=seeker_text,
        callback_data=f"set_participant_role_{game_id}_{participant_id}_seeker"
    ))
    
    # Размещаем кнопки ролей
    buttons.append(role_buttons)
    
    # Кнопка сброса роли (если роль назначена)
    if current_role:
        buttons.append([InlineKeyboardButton(
            text="❌ Убрать роль",
            callback_data=f"set_participant_role_{game_id}_{participant_id}_none"
        )])
    
    # Кнопка возврата
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к списку участников",
        callback_data=f"assign_roles_manual_{game_id}"
    )])
    
    return InlineKeyboardMarkup(buttons)

def get_available_users_keyboard(game_id, users):
    """Клавиатура для выбора пользователей для добавления в игру"""
    buttons = []
    
    for user in users:
        button_text = f"{user['name']}"
        if user.get('district'):
            button_text += f" ({user['district']})"
        
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"confirm_add_participant_{game_id}_{user['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к участникам",
        callback_data=f"manage_participants_{game_id}"
    )])
    
    return InlineKeyboardMarkup(buttons)
 