from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from src.services.user_context_service import UserContextService
from src.services.game_service import GameService
from src.keyboards.reply import get_contextual_main_keyboard, get_game_location_keyboard
from src.keyboards.inline import get_game_actions_keyboard

async def handle_my_game_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки 'Моя игра' - показывает информацию о текущей игре пользователя"""
    user_id = update.effective_user.id
    
    try:
        game_context = UserContextService.get_user_game_context(user_id)
        
        if not game_context.game:
            await update.message.reply_text(
                "❌ У вас нет активных игр",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        
        game = game_context.game
        participant = game_context.participant
        
        # Формируем информацию об игре
        game_info = (
            f"🎮 <b>Ваша игра</b>\n\n"
            f"📍 <b>Район:</b> {game.district}\n"
            f"⏰ <b>Время:</b> {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📊 <b>Статус:</b> {get_game_status_text(game.status)}\n"
            f"👥 <b>Участников:</b> {len(game.participants)}/{game.max_participants}\n"
        )
        
        if participant and participant.role:
            game_info += f"🎭 <b>Ваша роль:</b> {get_role_text(participant.role)}\n"
        
        if game.description:
            game_info += f"\n📝 <b>Описание:</b>\n{game.description}\n"
        
        # Добавляем информацию в зависимости от статуса игры
        if game_context.status == UserContextService.STATUS_REGISTERED:
            game_info += f"\n⏳ Ожидание начала игры"
        elif game_context.status == UserContextService.STATUS_IN_GAME:
            game_info += f"\n🔥 Игра в процессе!"
            if game.started_at:
                game_info += f"\n🚀 Начата: {game.started_at.strftime('%H:%M')}"
        elif game_context.status == UserContextService.STATUS_GAME_FINISHED:
            game_info += f"\n✅ Игра завершена"
            if game.ended_at:
                game_info += f"\n🏁 Завершена: {game.ended_at.strftime('%H:%M')}"
        
        # Формируем клавиатуру действий
        keyboard = get_game_actions_keyboard(game, is_participant=True)
        
        await update.message.reply_text(
            game_info,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Моя игра' для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при загрузке информации об игре",
            reply_markup=get_contextual_main_keyboard(user_id)
        )

async def handle_game_status_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки 'Статус игры' - показывает подробную информацию о текущем состоянии игры"""
    user_id = update.effective_user.id
    
    try:
        game_context = UserContextService.get_user_game_context(user_id)
        
        if not game_context.game:
            await update.message.reply_text(
                "❌ У вас нет активных игр",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        
        game = game_context.game
        participants = game.participants
        
        # Формируем подробную информацию
        status_info = (
            f"📊 <b>СТАТУС ИГРЫ</b>\n\n"
            f"🎮 <b>Игра #{game.id}</b>\n"
            f"📍 <b>Район:</b> {game.district}\n"
            f"📊 <b>Текущий статус:</b> {get_game_status_text(game.status)}\n"
        )
        
        # Информация о времени
        if game.scheduled_at:
            status_info += f"⏰ <b>Запланирована:</b> {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
        if game.started_at:
            status_info += f"🚀 <b>Начата:</b> {game.started_at.strftime('%d.%m.%Y %H:%M')}\n"
        if game.ended_at:
            status_info += f"🏁 <b>Завершена:</b> {game.ended_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        # Информация об участниках
        status_info += f"\n👥 <b>Участники ({len(participants)}/{game.max_participants}):</b>\n"
        
        drivers = [p for p in participants if p.role and p.role.value == 'driver']
        seekers = [p for p in participants if p.role and p.role.value == 'seeker']
        no_role = [p for p in participants if not p.role]
        
        if drivers:
            status_info += f"🚗 <b>Водители ({len(drivers)}):</b>\n"
            for driver in drivers:
                user_mark = "👤 " if driver.user.telegram_id == user_id else ""
                status_info += f"• {user_mark}{driver.user.name}\n"
        
        if seekers:
            status_info += f"🔍 <b>Искатели ({len(seekers)}):</b>\n"
            for seeker in seekers:
                user_mark = "👤 " if seeker.user.telegram_id == user_id else ""
                status_info += f"• {user_mark}{seeker.user.name}\n"
        
        if no_role:
            status_info += f"⏰ <b>Ожидают распределения ролей ({len(no_role)}):</b>\n"
            for participant in no_role:
                user_mark = "👤 " if participant.user.telegram_id == user_id else ""
                status_info += f"• {user_mark}{participant.user.name}\n"
        
        await update.message.reply_text(
            status_info,
            parse_mode="HTML",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Статус игры' для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при загрузке статуса игры",
            reply_markup=get_contextual_main_keyboard(user_id)
        )

async def handle_send_location_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки отправки локации"""
    user_id = update.effective_user.id
    
    try:
        game_context = UserContextService.get_user_game_context(user_id)
        
        if game_context.status != UserContextService.STATUS_IN_GAME:
            await update.message.reply_text(
                "❌ Отправка локации доступна только во время активной игры",
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
        
        # Формируем инструкции в зависимости от роли
        if role == 'driver':
            location_text = (
                f"📍 <b>Отправка геолокации - Водитель</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n\n"
                f"🚗 <b>Инструкции для водителя:</b>\n"
                f"• Найдите укромное место для пряток\n"
                f"• Убедитесь, что место безопасно\n"
                f"• Нажмите кнопку ниже для отправки геолокации\n"
                f"• После отправки ждите искателей\n\n"
            )
        else:
            location_text = (
                f"📍 <b>Отправка геолокации - Искатель</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n\n"
                f"🔍 <b>Инструкции для искателя:</b>\n"
                f"• Отправляйте свою позицию для координации\n"
                f"• Это поможет другим искателям\n"
                f"• Нажмите кнопку ниже для отправки геолокации\n"
                f"• Продолжайте поиск водителя\n\n"
            )
        
        # Показываем зону игры если она есть
        if hasattr(game, 'has_game_zone') and game.has_game_zone:
            zone_info = game.zone_info
            location_text += (
                f"🎯 <b>Игровая зона:</b>\n"
                f"• Центр: {zone_info['center_lat']:.4f}, {zone_info['center_lon']:.4f}\n"
                f"• Радиус: {zone_info['radius']} метров\n"
                f"• Площадь: {zone_info['area_km2']} км²\n\n"
            )
        
        location_text += f"📱 Нажмите кнопку ниже для отправки геолокации"
        
        # Создаем inline клавиатуру с быстрыми действиями
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        if role == 'driver':
            inline_buttons = [
                [InlineKeyboardButton("📸 Фото места", callback_data=f"photo_place_{game.id}")],
                [InlineKeyboardButton("🚗 Меня нашли", callback_data=f"found_seeker_{game.id}")],
                [InlineKeyboardButton("📊 Статус игры", callback_data=f"game_status_{game.id}")]
            ]
        else:
            inline_buttons = [
                [InlineKeyboardButton("📸 Фото находки", callback_data=f"photo_find_{game.id}")],
                [InlineKeyboardButton("🔍 Нашел водителя", callback_data=f"found_driver_{game.id}")],
                [InlineKeyboardButton("📊 Статус игры", callback_data=f"game_status_{game.id}")]
            ]
        
        inline_keyboard = InlineKeyboardMarkup(inline_buttons)
        
        # Отправляем сообщение с кнопкой геолокации и inline кнопками
        await update.message.reply_text(
            location_text,
            parse_mode="HTML",
            reply_markup=inline_keyboard
        )
        
        # Дополнительно отправляем keyboard для геолокации
        await update.message.reply_text(
            "👇 Используйте кнопку ниже для отправки геолокации:",
            reply_markup=get_game_location_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки отправки локации для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при подготовке отправки локации",
            reply_markup=get_contextual_main_keyboard(user_id)
        )

async def handle_game_results_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки 'Результаты игры'"""
    user_id = update.effective_user.id
    
    try:
        game_context = UserContextService.get_user_game_context(user_id)
        
        if not game_context.game or game_context.status != UserContextService.STATUS_GAME_FINISHED:
            await update.message.reply_text(
                "❌ Результаты доступны только для завершенных игр",
                reply_markup=get_contextual_main_keyboard(user_id)
            )
            return
        
        game = game_context.game
        participant = game_context.participant
        
        results_text = (
            f"📊 <b>РЕЗУЛЬТАТЫ ИГРЫ</b>\n\n"
            f"🎮 <b>Игра #{game.id}</b> в районе {game.district}\n"
            f"⏰ <b>Длительность:</b> "
        )
        
        if game.started_at and game.ended_at:
            duration = game.ended_at - game.started_at
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            results_text += f"{hours}ч {minutes}м\n"
        else:
            results_text += "Неизвестно\n"
        
        if participant and participant.role:
            results_text += f"🎭 <b>Ваша роль:</b> {get_role_text(participant.role)}\n"
        
        results_text += f"\n🏆 <b>Итоги игры:</b>\n"
        results_text += f"✅ Игра успешно завершена\n"
        results_text += f"👥 Участвовало игроков: {len(game.participants)}\n"
        
        # Здесь можно добавить дополнительную статистику, когда она будет реализована
        
        await update.message.reply_text(
            results_text,
            parse_mode="HTML",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки результатов игры для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при загрузке результатов игры",
            reply_markup=get_contextual_main_keyboard(user_id)
        )

def get_game_status_text(status) -> str:
    """Получить текстовое представление статуса игры"""
    status_texts = {
        'recruiting': '📝 Набор участников',
        'upcoming': '⏰ Скоро начнется',
        'hiding_phase': '🏃 Фаза пряток',
        'searching_phase': '🔍 Фаза поиска',
        'completed': '✅ Завершена',
        'canceled': '❌ Отменена'
    }
    return status_texts.get(status.value if hasattr(status, 'value') else str(status), str(status))

def get_role_text(role) -> str:
    """Получить текстовое представление роли"""
    role_texts = {
        'driver': '🚗 Водитель',
        'seeker': '🔍 Искатель',
        'observer': '👁 Наблюдатель'
    }
    return role_texts.get(role.value if hasattr(role, 'value') else str(role), str(role)) 