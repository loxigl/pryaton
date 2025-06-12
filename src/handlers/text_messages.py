from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from loguru import logger

from src.services.user_service import UserService
from src.services.settings_service import SettingsService

from src.handlers.games import games_command, my_games_command
from src.handlers.admin import admin_command
from src.handlers.monitoring import monitoring_command
from src.handlers.scheduler_admin import scheduler_monitor_command
from src.handlers.contextual_actions import (
    handle_my_game_button,
    handle_game_status_button, 
    handle_send_location_button,
    handle_game_results_button
)
from src.keyboards.reply import get_contextual_main_keyboard

async def show_monitoring_basic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Базовое меню мониторинга без ConversationHandler"""
    try:
        from src.services.monitoring_service import MonitoringService
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        # Получаем общую статистику
        stats = MonitoringService.get_active_games_stats()
        
        stats_text = (
            f"📊 <b>МОНИТОРИНГ СИСТЕМЫ</b>\n\n"
            f"🎮 <b>Активные игры:</b> {stats.get('active_games_count', 0)}\n"
            f"📅 <b>Игры сегодня:</b> {stats.get('today_games_count', 0)}\n"
            f"👥 <b>Всего участий:</b> {stats.get('total_participants', 0)}\n"
            f"👤 <b>Уникальных игроков:</b> {stats.get('unique_players', 0)}\n\n"
        )
        
        # Добавляем статистику по статусам игр
        games_by_status = stats.get('games_by_status', {})
        if games_by_status:
            stats_text += f"📈 <b>Игры по статусам:</b>\n"
            status_names = {
                'recruiting': '📝 Набор',
                'upcoming': '⏰ Скоро',
                'hiding_phase': '🏃 Фаза пряток',
                'searching_phase': '🔍 Фаза поиска',
                'completed': '✅ Завершены',
                'canceled': '❌ Отменены'
            }
            
            for status, count in games_by_status.items():
                status_name = status_names.get(status, status)
                stats_text += f"• {status_name}: {count}\n"
        
        # Создаем клавиатуру
        keyboard = [
            [InlineKeyboardButton("🎮 Активные игры", callback_data="mon_active_games")],
            [InlineKeyboardButton("📊 Статистика игроков", callback_data="mon_player_stats")],
            [InlineKeyboardButton("🗺 Статистика районов", callback_data="mon_district_stats")],
            [InlineKeyboardButton("📝 Последние активности", callback_data="mon_recent_activities")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="mon_refresh")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="mon_exit")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка при загрузке мониторинга: {e}",
            reply_markup=get_contextual_main_keyboard(update.effective_user.id)
        )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений с клавиатуры"""
    text = update.message.text
    user_id = update.effective_user.id
    
    logger.info(f"Пользователь {user_id} нажал кнопку: '{text}'")
    
    # Проверяем текст сообщения и вызываем соответствующий обработчик
    if text == "🎮 Доступные игры" or text == "🎲 Доступные игры":
        logger.info(f"Вызываем games_command для пользователя {user_id}")
        await games_command(update, context)
    elif text == "🎯 Мои игры" or text == "🎯 Все мои игры":
        logger.info(f"Вызываем my_games_command для пользователя {user_id}")
        await my_games_command(update, context)
    elif text == "🎮 Моя игра":
        logger.info(f"Вызываем handle_my_game_button для пользователя {user_id}")
        await handle_my_game_button(update, context)
    elif text == "📊 Моя игра" or text == "🎮 Статус игры":
        logger.info(f"Вызываем handle_game_status_button для пользователя {user_id}")
        await handle_game_status_button(update, context)
    elif text in ["📍 Отправить локацию", "📍 Моя позиция"]:
        logger.info(f"Вызываем handle_send_location_button для пользователя {user_id}")
        await handle_send_location_button(update, context)
    elif text == "📊 Результаты игры":
        logger.info(f"Вызываем handle_game_results_button для пользователя {user_id}")
        await handle_game_results_button(update, context)
    elif text == "🎮 Новые игры":
        # Перенаправляем на доступные игры
        logger.info(f"Перенаправляем на games_command для пользователя {user_id}")
        await games_command(update, context)
    elif text == "🔑 Админ-панель":
        logger.info(f"Вызываем admin_command для пользователя {user_id}")
        await admin_command(update, context)
    elif text == "📊 Мониторинг":
        # Проверяем админ права и показываем мониторинг
        if not UserService.is_admin(user_id):
            logger.warning(f"Пользователь {user_id} попытался получить доступ к мониторингу без прав")
            await update.message.reply_text(
                "❌ Доступ запрещен. Только для администраторов.",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        
        logger.info(f"Показываем мониторинг для админа {user_id}")
        # Показываем базовое меню мониторинга
        await show_monitoring_basic(update, context)
    elif text == "📅 События планировщика":
        # Проверяем админ права и показываем мониторинг планировщика
        if not UserService.is_admin(user_id):
            logger.warning(f"Пользователь {user_id} попытался получить доступ к планировщику без прав")
            await update.message.reply_text(
                "❌ Доступ запрещен. Только для администраторов.",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        
        logger.info(f"Показываем мониторинг планировщика для админа {user_id}")
        # Показываем мониторинг планировщика
        await scheduler_monitor_command(update, context)
    elif text == "👤 Мой профиль":
        logger.info(f"Показываем профиль для пользователя {user_id}")
        await show_profile(update, context)
    elif text == "ℹ️ Помощь" or text == "ℹ️ Правила":
        logger.info(f"Показываем помощь для пользователя {user_id}")
        await show_help(update, context)
    elif text == "🏠 Главное меню":
        logger.info("Нажата кнопка главного меню")
        # Проверяем заполненность новых полей автомобиля
        user, _ = UserService.get_user_by_telegram_id(user_id)
        if not user or not user.car_brand or not user.car_color or not user.car_number:
            # Инициируем до-заполнение профиля через FSM регистрации
            from src.handlers.start import (
                process_car_brand, process_car_color, process_car_number,
                ENTER_CAR_BRAND, ENTER_CAR_COLOR, ENTER_CAR_NUMBER
            )
            context.user_data["name"] = user.name if user else ""
            context.user_data["phone"] = user.phone if user else ""
            context.user_data["district"] = user.district if user else ""
            context.user_data["role"] = user.default_role if user else ""
            # Определяем, с какого этапа начинать
            if not user or not user.car_brand:
                car_brand_text = (
                    f"🚗 <b>Укажите марку автомобиля</b>\nВведите название марки вашего автомобиля (например, Toyota, BMW и т.д.)."
                )
                from telegram import ReplyKeyboardMarkup
                keyboard = ReplyKeyboardMarkup([
                    ["⬅️ Назад"],
                    ["❌ Отмена"]
                ], resize_keyboard=True)
                await update.message.reply_text(
                    car_brand_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return ENTER_CAR_BRAND
            elif not user.car_color:
                car_color_text = (
                    f"🎨 <b>Укажите цвет автомобиля</b>\nВведите цвет вашего автомобиля (например, белый, черный, красный и т.д.)."
                )
                from telegram import ReplyKeyboardMarkup
                keyboard = ReplyKeyboardMarkup([
                    ["⬅️ Назад"],
                    ["❌ Отмена"]
                ], resize_keyboard=True)
                await update.message.reply_text(
                    car_color_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return ENTER_CAR_COLOR
            elif not user.car_number:
                car_number_text = (
                    f"🔢 <b>Укажите государственный номер автомобиля</b>\nВведите гос. номер вашего автомобиля (например, А123БВ777)."
                )
                from telegram import ReplyKeyboardMarkup
                keyboard = ReplyKeyboardMarkup([
                    ["⬅️ Назад"],
                    ["❌ Отмена"]
                ], resize_keyboard=True)
                await update.message.reply_text(
                    car_number_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return ENTER_CAR_NUMBER
        # Если все поля заполнены, показываем главное меню
        logger.info(f"Показываем контекстное главное меню для пользователя {user_id}")
        welcome_text = "🏠 <b>Главное меню</b>\n\nВыберите действие:"
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_contextual_main_keyboard(user_id),
            parse_mode="HTML"
        )
    elif text.startswith("⏰"):
        # Это информационная кнопка с расписанием игры - показываем детали
        logger.info(f"Показываем детали игры для пользователя {user_id}")
        await handle_my_game_button(update, context)
    elif text in ["⏰ Ожидание роли", "⏰ Ожидание старта"]:
        # Информационные кнопки - показываем статус игры
        logger.info(f"Показываем статус игры для пользователя {user_id}")
        await handle_game_status_button(update, context)
    elif text in ["📸 Фото места", "📸 Фото находки"]:
        # Обработка кнопок фотографий - интегрируем с реальной логикой
        logger.info(f"Обработка кнопки фото для пользователя {user_id}: {text}")
        await handle_photo_button_action(update, context, text)
    elif text in ["🚗 Меня нашли", "🔍 Я нашел водителя"]:
        # Обработка кнопок завершения игры - интегрируем с реальной логикой
        logger.info(f"Обработка кнопки завершения для пользователя {user_id}: {text}")
        await handle_game_completion_button_action(update, context, text)
    elif text == "⚠️ Нужна помощь":
        # Обработка кнопки помощи в игре
        await show_game_help(update, context)
    elif text == "🏆 Мои достижения":
        # Показываем информацию о достижениях
        await show_achievements(update, context)
    else:
        # Неизвестное сообщение - показываем контекстное главное меню
        logger.warning(f"Неизвестное сообщение от пользователя {user_id}: '{text}'")
        await update.message.reply_text(
            "Я не понимаю это сообщение. Используйте кнопки для навигации:",
            reply_markup=get_contextual_main_keyboard(user_id)
        )

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает профиль пользователя"""
    user_id = update.effective_user.id
    
    # Получаем информацию о пользователе
    user, participations = UserService.get_user_by_telegram_id(user_id)
    
    if not user:
        await update.message.reply_text(
            "❌ Ошибка: пользователь не найден. Пожалуйста, нажмите 🏠 Главное меню для перезапуска",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        return
    
    # Формируем информацию о профиле
    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"<b>Имя:</b> {user.name}\n"
        f"<b>Район:</b> {user.district}\n"
        f"<b>Роль по умолчанию:</b> {get_role_text(user.default_role)}\n"
    )
    
    if user.phone:
        profile_text += f"<b>Телефон:</b> {user.phone}\n"
    
    # Добавляем статистику участия в играх
    games_count = len(participations)
    profile_text += f"\n<b>Участие в играх:</b> {games_count}"
    
    await update.message.reply_text(
        profile_text,
        parse_mode="HTML",
        reply_markup=get_contextual_main_keyboard(user_id)
    )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает справку по использованию бота"""
    user_id = update.effective_user.id
    
    help_text = (
        "ℹ️ <b>Справка по использованию бота</b>\n\n"
        "<b>Основные функции:</b>\n"
        "🎮 <b>Доступные игры</b> - Показать список игр для записи\n"
        "🎯 <b>Мои игры</b> - Показать ваши игры\n"
        "👤 <b>Мой профиль</b> - Информация о вашем профиле\n"
        "🏠 <b>Главное меню</b> - Вернуться на главную страницу\n\n"
        
        "<b>Как играть:</b>\n"
        "1. Записывайтесь на игры через меню 'Доступные игры'\n"
        "2. Получайте уведомления о начале игры\n"
        "3. Участвуйте в играх по геолокации\n"
        "4. Отправляйте фотографии для подтверждения\n\n"
        
        "<b>Контекстное меню:</b>\n"
        "Меню автоматически изменяется в зависимости от вашего статуса:\n"
        "• Если вы записаны на игру - появляется кнопка 'Моя игра'\n"
        "• Во время игры - специальные кнопки для вашей роли\n"
        "• После игры - кнопки результатов и достижений\n\n"
    )
    
    # Добавляем команды для администраторов
    if UserService.is_admin(user_id):
        help_text += (
            "<b>Функции администратора:</b>\n"
            "🔑 <b>Админ-панель</b> - Управление играми и настройками\n"
            "• Создание новых игр\n"
            "• Управление участниками\n"
            "• Настройка районов и ролей\n"
        )
    
    await update.message.reply_text(
        help_text,
        parse_mode="HTML",
        reply_markup=get_contextual_main_keyboard(user_id)
    )

async def show_game_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает помощь во время игры"""
    user_id = update.effective_user.id
    
    from src.services.user_context_service import UserContextService
    game_context = UserContextService.get_user_game_context(user_id)
    
    if game_context.status != UserContextService.STATUS_IN_GAME:
        await update.message.reply_text(
            "⚠️ Помощь в игре доступна только во время активной игры",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        return
    
    role_help = ""
    if game_context.participant and game_context.participant.role:
        role = game_context.participant.role.value
        if role == 'driver':
            role_help = (
                "🚗 <b>Советы для водителя:</b>\n"
                "• Найдите укромное место для пряток\n"
                "• Отправляйте геолокацию для подтверждения\n"
                "• Делайте фото места для подтверждения\n"
                "• Будьте осторожны, искатели уже ищут!\n\n"
            )
        elif role == 'seeker':
            role_help = (
                "🔍 <b>Советы для искателя:</b>\n"
                "• Изучите район игры внимательно\n"
                "• Отправляйте свою позицию для координации\n"
                "• Делайте фото находок\n"
                "• Работайте в команде с другими искателями\n\n"
            )
    
    help_text = (
        f"⚠️ <b>ПОМОЩЬ В ИГРЕ</b>\n\n"
        f"{role_help}"
        f"<b>Общие правила:</b>\n"
        f"• Соблюдайте правила дорожного движения\n"
        f"• Будьте вежливы с другими участниками\n"
        f"• При проблемах свяжитесь с администрацией\n"
        f"• Не покидайте указанную игровую зону\n\n"
        f"<b>Экстренные ситуации:</b>\n"
        f"В случае серьезных проблем обратитесь к администратору через главное меню."
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode="HTML",
        reply_markup=get_contextual_main_keyboard(user_id)
    )

async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает достижения пользователя"""
    user_id = update.effective_user.id
    
    # Пока что базовая версия достижений
    achievements_text = (
        f"🏆 <b>ВАШИ ДОСТИЖЕНИЯ</b>\n\n"
        f"📊 Эта функция будет расширена в следующих обновлениях.\n\n"
        f"Пока что вы можете посмотреть количество ваших игр в разделе 'Мой профиль'."
    )
    
    await update.message.reply_text(
        achievements_text,
        parse_mode="HTML",
        reply_markup=get_contextual_main_keyboard(user_id)
    )

def get_role_text(role) -> str:
    """Получить текстовое представление роли"""
    return SettingsService.get_role_display_name(role)

async def handle_photo_button_action(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str) -> None:
    """Обработка кнопок фотографий"""
    user_id = update.effective_user.id
    
    try:
        from src.services.user_context_service import UserContextService
        game_context = UserContextService.get_user_game_context(user_id)
        
        if game_context.status != UserContextService.STATUS_IN_GAME:
            await update.message.reply_text(
                "📸 Отправка фотографий доступна только во время активной игры",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        
        game = game_context.game
        participant = game_context.participant
        
        if not participant or not participant.role:
            await update.message.reply_text(
                "❌ Не удалось определить вашу роль в игре",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        
        role = participant.role.value
        
        if button_text == "📸 Фото места" and role == 'driver':
            photo_text = (
                f"📸 <b>Отправка фото места - Водитель</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n\n"
                f"🚗 <b>Инструкции:</b>\n"
                f"• Сделайте фото своего места пряток\n"
                f"• Фото должно показывать машину и окружение\n"
                f"• Это поможет искателям вас найти\n\n"
                f"📱 Просто сделайте фото и отправьте его в этот чат"
            )
        elif button_text == "📸 Фото находки" and role == 'seeker':
            photo_text = (
                f"📸 <b>Отправка фото находки - Искатель</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n\n"
                f"🔍 <b>Инструкции:</b>\n"
                f"• Сделайте фото найденной машины\n"
                f"• Фото должно четко показывать машину\n"
                f"• Водитель должен подтвердить находку\n\n"
                f"📱 Просто сделайте фото и отправьте его в этот чат"
            )
        else:
            await update.message.reply_text(
                f"❌ Кнопка '{button_text}' недоступна для вашей роли",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        
        await update.message.reply_text(
            photo_text,
            parse_mode="HTML",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки фото для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке запроса",
            reply_markup=get_contextual_main_keyboard(user_id)
        )

async def handle_game_completion_button_action(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str) -> None:
    """Обработка кнопок завершения игры"""
    user_id = update.effective_user.id
    try:
        from src.services.user_context_service import UserContextService
        game_context = UserContextService.get_user_game_context(user_id)
        if game_context.status != UserContextService.STATUS_IN_GAME:
            await update.message.reply_text(
                "🏁 Завершение игры доступно только во время активной игры",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        game = game_context.game
        participant = game_context.participant
        if not participant or not participant.role:
            await update.message.reply_text(
                "❌ Не удалось определить вашу роль в игре",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        role = participant.role.value
        if button_text == "🚗 Меня нашли" and role == 'driver':
            from src.services.game_service import GameService
            success = GameService.mark_participant_found(game.id, participant.user_id)
            if success:
                await update.message.reply_text(
                    f"🎉 <b>Находка подтверждена!</b>\n\n"
                    f"Вы отметили, что вас нашли в игре {game.district}.\n"
                    f"Все участники получат уведомление.\n\n"
                    f"Игра для вас завершена. Спасибо за участие!",
                    parse_mode="HTML",
                    reply_markup=get_contextual_main_keyboard(user_id)
                )
                await notify_participants_about_found_driver(context, game.id, participant.user.name)
                from src.handlers.callback_handler import check_game_completion_callback
                await check_game_completion_callback(context, game.id)
                # Обновляем клавиатуру после завершения игры
                await update.message.reply_text(
                    "🏁 Игра завершена! Возвращаемся в главное меню.",
                    reply_markup=get_contextual_main_keyboard(user_id)
                )
            else:
                await update.message.reply_text(
                    "❌ Не удалось отметить находку. Попробуйте еще раз.",
                    reply_markup=get_contextual_main_keyboard(user_id)
                )
        elif button_text == "🔍 Я нашел водителя" and role == 'seeker':
            await update.message.reply_text(
                f"🔍 <b>Сообщение о находке отправлено!</b>\n\n"
                f"Вы сообщили, что нашли водителя в игре {game.district}.\n"
                f"Водители получат уведомление.\n\n"
                f"Ожидайте подтверждения от водителя.",
                parse_mode="HTML",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            await notify_drivers_about_found(context, game.id, participant.user.name)
            # Обновляем клавиатуру после завершения игры для искателя
            await update.message.reply_text(
                "🏁 Игра завершена! Возвращаемся в главное меню.",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
        else:
            await update.message.reply_text(
                f"❌ Кнопка '{button_text}' недоступна для вашей роли",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки завершения для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке запроса",
            reply_markup=get_contextual_main_keyboard(user_id)
        )

async def notify_drivers_about_found(context: ContextTypes.DEFAULT_TYPE, game_id: int, seeker_name: str) -> None:
    """Уведомление водителей о том, что их нашли"""
    try:
        from src.services.game_service import GameService
        from src.services.user_service import UserService
        from src.models.game import GameStatus
        
        game = GameService.get_game_by_id(game_id)
        if not game or game.status not in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
            return
        
        # Находим всех водителей в игре
        for participant in game.participants:
            if participant.role and participant.role.value == 'driver' and not participant.is_found:
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            text=(
                                f"🔍 <b>Вас нашли!</b>\n\n"
                                f"🎮 <b>Игра:</b> {game.district}\n"
                                f"👤 <b>Нашел:</b> {seeker_name}\n\n"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления водителю {user.telegram_id}: {e}")
                        
    except Exception as e:
        logger.error(f"Ошибка уведомления водителей: {e}")

async def notify_participants_about_found_driver(context: ContextTypes.DEFAULT_TYPE, game_id: int, driver_name: str) -> None:
    """Уведомление участников о найденном водителе"""
    try:
        from src.services.game_service import GameService
        from src.services.user_service import UserService
        from src.models.game import GameStatus
        
        game = GameService.get_game_by_id(game_id)
        if not game or game.status not in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
            return
        
        # Уведомляем всех участников кроме найденного водителя
        for participant in game.participants:
            user, _ = UserService.get_user_by_id(participant.user_id)
            if user and user.name != driver_name:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"🎉 <b>Водитель найден!</b>\n\n"
                            f"🎮 <b>Игра:</b> {game.district}\n"
                            f"🚗 <b>Найден:</b> {driver_name}\n\n"
                            f"Игра продолжается - ищите других водителей!"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления участнику {user.telegram_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Ошибка уведомления участников: {e}")

# Обработчик всех текстовых сообщений
text_message_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_text_message
) 