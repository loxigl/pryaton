from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from loguru import logger
import re
from datetime import datetime

# Импортируем обработчики из разных модулей
from src.handlers.games import (
    game_button, join_game_button, leave_game_button, back_to_games_button, game_info_button,
    GAME_PATTERN, GAME_JOIN_PATTERN, GAME_LEAVE_PATTERN, GAME_INFO_PATTERN,
    SEND_LOCATION_PATTERN, SEND_PHOTO_PATTERN, FOUND_CAR_PATTERN, FOUND_ME_PATTERN, GAME_STATUS_PATTERN
)
from src.handlers.photo import handle_admin_photo_approval
from src.services.user_service import UserService

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Центральный обработчик всех callback'ов"""
    query = update.callback_query
    if not query:
        return
        
    data = query.data
    logger.info(f"Получен callback: {data} от пользователя {query.from_user.id}")
    
    try:
        # Обработка callback'ов мониторинга
        if data.startswith("mon_"):
            from src.handlers.monitoring import handle_monitoring_callback_direct
            await handle_monitoring_callback_direct(update, context)
            return
        
        # Обработка игровых callback'ов
        if re.match(GAME_PATTERN, data):
            await game_button(update, context)
        elif re.match(GAME_INFO_PATTERN, data):
            await game_info_button(update, context)
        elif re.match(GAME_JOIN_PATTERN, data):
            await join_game_button(update, context)
        elif re.match(GAME_LEAVE_PATTERN, data):
            await leave_game_button(update, context)
        elif data == "back_to_games":
            await back_to_games_button(update, context)
        elif data == "refresh_games":
            await back_to_games_button(update, context)  # Та же логика что и возврат
        
        # Обработка новых игровых callback'ов
        elif re.match(SEND_LOCATION_PATTERN, data):
            await handle_send_location_callback(update, context)
        elif re.match(SEND_PHOTO_PATTERN, data):
            await handle_send_photo_callback(update, context)
        elif re.match(FOUND_CAR_PATTERN, data):
            await handle_found_car_callback(update, context)
        elif re.match(FOUND_ME_PATTERN, data):
            await handle_found_me_callback(update, context)
        elif re.match(GAME_STATUS_PATTERN, data):
            await handle_game_status_callback(update, context)
        
        # Обработка дополнительных callback'ов из DynamicKeyboardService
        elif data.startswith("found_driver_"):
            await handle_found_driver_callback(update, context)
        elif data.startswith("found_seeker_"):
            await handle_found_seeker_callback(update, context)
        elif data.startswith("photo_place_"):
            await handle_photo_place_callback(update, context)
        elif data.startswith("photo_find_"):
            await handle_photo_find_callback(update, context)
        elif data.startswith("game_help_"):
            await handle_game_help_callback(update, context)
        
        # Обработка callback'ов фотографий
        elif data.startswith("photo_approve_") or data.startswith("photo_reject_"):
            await handle_admin_photo_approval(update, context)
        
        # Обработка callback'ов настроек игры
        elif data == "game_settings":
            await handle_game_settings_callback(update, context)
        elif data == "time_settings":
            await handle_time_settings_callback(update, context)
        elif data == "notification_settings":
            await handle_notification_settings_callback(update, context)
        elif data.startswith("toggle_"):
            await handle_toggle_setting_callback(update, context)
        elif data == "automation_settings":
            await handle_automation_settings_callback(update, context)
        elif data.startswith("set_hiding_time_") or data.startswith("set_searching_time_") or data.startswith("set_notification_time_") or data.startswith("set_min_participants_"):
            await handle_time_value_callback(update, context)
        
        # Обработка callback'ов конкретных настроек времени
        elif data in ["set_hiding_duration", "set_searching_duration", "set_notification_time", "set_min_participants"]:
            await handle_time_setting_select_callback(update, context)
        
        # Обработка кнопок возврата
        elif data == "back_to_admin":
            await handle_back_to_admin_callback(update, context)
        
        # Обработка сброса настроек
        elif data == "reset_settings":
            await handle_reset_settings_callback(update, context)
        
        # Обработка подтверждения сброса настроек
        elif data == "confirm_reset_settings":
            await handle_confirm_reset_settings_callback(update, context)
        
        # Обработка других callback'ов геолокации
        elif data == "cancel_location":
            await query.answer("Отправка геолокации отменена.")
            await query.edit_message_text("Отправка геолокации отменена.")
        
        else:
            # Неизвестный callback
            logger.warning(f"Неизвестный callback: {data}")
            await query.answer("Неизвестная команда")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке callback {data}: {e}")
        await query.answer("Произошла ошибка. Попробуйте еще раз.")

async def handle_send_location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а отправки геолокации"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID игры
    match = re.match(SEND_LOCATION_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    user_id = query.from_user.id
    
    try:
        from src.services.game_service import GameService
        from src.keyboards.reply import get_game_location_keyboard
        
        game = GameService.get_game_by_id(game_id)
        if not game:
            await query.edit_message_text("❌ Игра не найдена")
            return
        
        # Получаем роль пользователя в игре
        user, _ = UserService.get_user_by_telegram_id(user_id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return
        
        participant = next(
            (p for p in game.participants if p.user_id == user.id),
            None
        )
        
        if not participant:
            await query.edit_message_text("❌ Вы не участвуете в этой игре")
            return
        
        role = participant.role
        
        # Формируем инструкции в зависимости от роли
        if role.value == 'driver':
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
        if game.has_game_zone:
            zone_info = game.zone_info
            location_text += (
                f"🎯 <b>Игровая зона:</b>\n"
                f"• Центр: {zone_info['center_lat']:.4f}, {zone_info['center_lon']:.4f}\n"
                f"• Радиус: {zone_info['radius']} метров\n"
                f"• Площадь: {zone_info['area_km2']} км²\n\n"
            )
        
        location_text += f"📱 Используйте кнопку 'Отправить геолокацию' в главном меню"
        
        await query.edit_message_text(
            location_text,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки отправки геолокации: {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def handle_send_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а отправки фото"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID игры
    match = re.match(SEND_PHOTO_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    user_id = query.from_user.id
    
    try:
        from src.services.game_service import GameService
        
        game = GameService.get_game_by_id(game_id)
        if not game:
            await query.edit_message_text("❌ Игра не найдена")
            return
        
        # Получаем роль пользователя в игре
        user, _ = UserService.get_user_by_telegram_id(user_id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return
        
        participant = next(
            (p for p in game.participants if p.user_id == user.id),
            None
        )
        
        if not participant:
            await query.edit_message_text("❌ Вы не участвуете в этой игре")
            return
        
        role = participant.role
        
        # Формируем инструкции в зависимости от роли
        if role.value == 'driver':
            photo_text = (
                f"📸 <b>Отправка фото - Водитель</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n\n"
                f"🚗 <b>Инструкции для водителя:</b>\n"
                f"• Сделайте фото своего места пряток\n"
                f"• Фото должно показывать машину и окружение\n"
                f"• Это поможет искателям вас найти\n"
                f"• Отправьте фото через обычное сообщение\n\n"
                f"📱 Просто сделайте фото и отправьте его в этот чат"
            )
        else:
            photo_text = (
                f"📸 <b>Отправка фото - Искатель</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n\n"
                f"🔍 <b>Инструкции для искателя:</b>\n"
                f"• Сделайте фото найденной машины\n"
                f"• Фото должно четко показывать машину\n"
                f"• Водитель должен подтвердить находку\n"
                f"• Отправьте фото через обычное сообщение\n\n"
                f"📱 Просто сделайте фото и отправьте его в этот чат"
            )
        
        await query.edit_message_text(
            photo_text,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки отправки фото: {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def handle_found_car_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а 'Нашел машину' (искатель)"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID игры
    match = re.match(FOUND_CAR_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    user_id = query.from_user.id
    
    try:
        from src.services.game_service import GameService
        game = GameService.get_game_by_id(game_id)
        if not game:
            await query.edit_message_text("❌ Игра не найдена")
            return
        
        GameService.mark_participant_found(game_id, user_id)
        user, _ = UserService.get_user_by_telegram_id(user_id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return

        await query.edit_message_text(
            f"🎉 <b>Отлично!</b>\n\n"
            f"Вы отметили, что нашли машину в игре {game.district}.\n"
            f"Водитель получит уведомление.\n\n"
            f"Ожидайте подтверждения от водителя через фотографию.",
            parse_mode="HTML"
        )
        
        # Уведомляем водителей
        await notify_drivers_about_found(context, game_id, user.name)
        
        # Проверяем завершение игры
        await check_game_completion_callback(context, game_id)
        
    except Exception as e:
        logger.error(f"Ошибка обработки 'Нашел машину': {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def handle_found_me_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а 'Меня нашли' (водитель)"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID игры
    match = re.match(FOUND_ME_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    user_id = query.from_user.id
    
    try:
        from src.services.game_service import GameService
        
        game = GameService.get_game_by_id(game_id)
        if not game:
            await query.edit_message_text("❌ Игра не найдена")
            return
        
        user, _ = UserService.get_user_by_telegram_id(user_id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return
        
        participant = next(
            (p for p in game.participants if p.user_id == user.id),
            None
        )
        
        if not participant or participant.role.value != 'driver':
            await query.edit_message_text("❌ Эта функция доступна только водителям")
            return
        

        GameService.mark_participant_found(game_id, user_id)
        
        await query.edit_message_text(
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"Вас нашли в игре {game.district}!\n"
            f"Игра для вас завершена.\n\n"
            f"Спасибо за участие!",
            parse_mode="HTML"
        )
        
        # Уведомляем всех участников
        await notify_participants_about_found_driver(context, game_id, user.name)
        
        # Проверяем завершение игры
        await check_game_completion_callback(context, game_id)
        
    except Exception as e:
        logger.error(f"Ошибка обработки 'Меня нашли': {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def handle_game_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а статуса игры"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID игры
    match = re.match(GAME_STATUS_PATTERN, query.data)
    if not match:
        return
    
    game_id = int(match.group(1))
    user_id = query.from_user.id
    
    try:
        from src.services.user_context_service import UserContextService
        from src.services.game_service import GameService
        
        game_context = UserContextService.get_user_game_context(user_id)
        
        if not game_context.game or game_context.game.id != game_id:
            await query.edit_message_text("❌ У вас нет доступа к этой игре")
            return
        
        game = game_context.game
        participants = game.participants
        
        # Формируем подробную информацию
        status_info = (
            f"📊 <b>СТАТУС ИГРЫ</b>\n\n"
            f"🎮 <b>Игра #{game.id}</b>\n"
            f"📍 <b>Район:</b> {game.district}\n"
            f"📊 <b>Текущий статус:</b> {_get_game_status_text(game.status)}\n"
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
        
        await query.edit_message_text(
            status_info,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке статуса игры для пользователя {user_id}: {e}")
        await query.edit_message_text("❌ Произошла ошибка при загрузке статуса игры")

async def handle_found_driver_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а 'Я нашел водителя' (искатель)"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        from src.services.user_context_service import UserContextService
        from src.services.game_service import GameService
        from src.services.user_service import UserService
        
        game_context = UserContextService.get_user_game_context(user_id)
        
        if game_context.status != UserContextService.STATUS_IN_GAME:
            await query.edit_message_text("❌ Эта функция доступна только во время активной игры")
            return
        
        game = game_context.game
        participant = game_context.participant
        
        if not participant or not participant.role or participant.role.value != 'seeker':
            await query.edit_message_text("❌ Эта функция доступна только искателям")
            return
        
        await query.edit_message_text(
            f"🔍 <b>Сообщение о находке отправлено!</b>\n\n"
            f"Вы сообщили, что нашли водителя в игре {game.district}.\n"
            f"Водители получат уведомление и должны подтвердить находку.\n\n"
            f"Ожидайте подтверждения от водителя.",
            parse_mode="HTML"
        )
        
        # Уведомляем водителей
        await notify_drivers_about_found_inline(context, game.id, participant.user.name)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке 'Нашел водителя': {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def handle_found_seeker_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а 'Меня нашли' (водитель)"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        from src.services.user_context_service import UserContextService
        from src.services.game_service import GameService
        from src.services.user_service import UserService
        
        game_context = UserContextService.get_user_game_context(user_id)
        
        if game_context.status != UserContextService.STATUS_IN_GAME:
            await query.edit_message_text("❌ Эта функция доступна только во время активной игры")
            return
        
        game = game_context.game
        participant = game_context.participant
        
        if not participant or not participant.role or participant.role.value != 'driver':
            await query.edit_message_text("❌ Эта функция доступна только водителям")
            return
        
        # Отмечаем водителя как найденного
        success = GameService.mark_participant_found(game.id, participant.user_id)
        if success:
            await query.edit_message_text(
                f"🎉 <b>Находка подтверждена!</b>\n\n"
                f"Вы подтвердили, что вас нашли в игре {game.district}.\n"
                f"Все участники получат уведомление.\n\n"
                f"Игра для вас завершена. Спасибо за участие!",
                parse_mode="HTML"
            )
            
            # Уведомляем всех участников
            await notify_participants_about_found_driver_inline(context, game.id, participant.user.name)
            
            # Проверяем завершение игры
            await check_game_completion_inline(context, game.id)
        else:
            await query.edit_message_text("❌ Не удалось отметить находку. Попробуйте еще раз.")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке 'Меня нашли': {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def handle_photo_place_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а фото места (водитель)"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        from src.services.user_context_service import UserContextService
        
        game_context = UserContextService.get_user_game_context(user_id)
        
        if game_context.status != UserContextService.STATUS_IN_GAME:
            await query.edit_message_text("❌ Отправка фотографий доступна только во время активной игры")
            return
        
        game = game_context.game
        participant = game_context.participant
        
        if not participant or not participant.role or participant.role.value != 'driver':
            await query.edit_message_text("❌ Эта функция доступна только водителям")
            return
        
        await query.edit_message_text(
            f"📸 <b>Отправка фото места - Водитель</b>\n\n"
            f"🎮 <b>Игра:</b> {game.district}\n\n"
            f"🚗 <b>Инструкции:</b>\n"
            f"• Сделайте фото своего места пряток\n"
            f"• Фото должно показывать машину и окружение\n"
            f"• Это поможет искателям вас найти\n\n"
            f"📱 Просто сделайте фото и отправьте его в этот чат",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото места: {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def handle_photo_find_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а фото находки (искатель)"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        from src.services.user_context_service import UserContextService
        
        game_context = UserContextService.get_user_game_context(user_id)
        
        if game_context.status != UserContextService.STATUS_IN_GAME:
            await query.edit_message_text("❌ Отправка фотографий доступна только во время активной игры")
            return
        
        game = game_context.game
        participant = game_context.participant
        
        if not participant or not participant.role or participant.role.value != 'seeker':
            await query.edit_message_text("❌ Эта функция доступна только искателям")
            return
        
        await query.edit_message_text(
            f"📸 <b>Отправка фото находки - Искатель</b>\n\n"
            f"🎮 <b>Игра:</b> {game.district}\n\n"
            f"🔍 <b>Инструкции:</b>\n"
            f"• Сделайте фото найденной машины\n"
            f"• Фото должно четко показывать машину\n"
            f"• Водитель должен подтвердить находку\n\n"
            f"📱 Просто сделайте фото и отправьте его в этот чат",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото находки: {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")

async def handle_game_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а помощи в игре"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    from src.services.user_context_service import UserContextService
    game_context = UserContextService.get_user_game_context(user_id)
    
    if game_context.status != UserContextService.STATUS_IN_GAME:
        await query.edit_message_text("⚠️ Помощь в игре доступна только во время активной игры")
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
    
    await query.edit_message_text(
        help_text,
        parse_mode="HTML"
    )

def _get_game_status_text(status) -> str:
    """Получить текстовое представление статуса игры"""
    status_texts = {
        'recruiting': '📝 Набор участников',
        'upcoming': '⏰ Скоро начнется',
        'hiding_phase': '🏃 Прятки',
        'searching_phase': '🔍 Поиск',
        'completed': '✅ Завершена',
        'canceled': '❌ Отменена'
    }
    return status_texts.get(status.value if hasattr(status, 'value') else str(status), str(status))

async def notify_drivers_about_found(context: ContextTypes.DEFAULT_TYPE, game_id: int, seeker_name: str) -> None:
    """Уведомление водителей о том, что их нашли"""
    try:
        from src.services.game_service import GameService
        
        game = GameService.get_game_by_id(game_id)
        if not game:
            return
        
        # Находим всех водителей в игре
        for participant in game.participants:
            if participant.role.value == 'driver':
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    try:
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            text=(
                                f"🔍 <b>Вас нашли!</b>\n\n"
                                f"🎮 <b>Игра:</b> {game.district}\n"
                                f"👤 <b>Нашел:</b> {seeker_name}\n\n"
                                f"Подтвердите находку нажав кнопку 'Меня нашли' в игровом интерфейсе."
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
        
        game = GameService.get_game_by_id(game_id)
        if not game:
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

async def check_game_completion_callback(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Проверка завершения игры и уведомление об этом"""
    try:
        from src.services.game_service import GameService
        from src.models.game import GameStatus
        
        logger.info(f"Проверка завершения игры {game_id}")
        
        game = GameService.get_game_by_id(game_id)
        if not game:
            logger.warning(f"Игра {game_id} не найдена")
            return
            
        logger.info(f"Статус игры {game_id}: {game.status}")
        
        if game.status not in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
            logger.info(f"Игра {game_id} не в активной фазе, пропускаем проверку")
            return
        
        # Проверяем, все ли водители найдены
        drivers_found = 0
        total_drivers = 0
        
        for participant in game.participants:
            if participant.role.value == 'driver':
                total_drivers += 1
                logger.info(f"Водитель {participant.user_id}: найден={participant.is_found}")
                if participant.is_found:
                    drivers_found += 1
        
        logger.info(f"Статистика игры {game_id}: найдено водителей {drivers_found}/{total_drivers}")
        
        # Если все водители найдены, завершаем игру
        if drivers_found >= total_drivers and total_drivers > 0:
            logger.info(f"Все водители найдены! Завершаем игру {game_id}")
            GameService.end_game(game_id)
            # Уведомляем всех участников о завершении игры
            await notify_game_completion_callback(context, game_id)
        else:
            logger.info(f"Игра {game_id} продолжается: {drivers_found}/{total_drivers} найдено")
            
    except Exception as e:
        logger.error(f"Ошибка проверки завершения игры: {e}")

async def notify_game_completion_callback(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Уведомление участников о завершении игры"""
    try:
        from src.services.game_service import GameService
        
        logger.info(f"Отправка уведомлений о завершении игры {game_id}")
        
        game = GameService.get_game_by_id(game_id)
        if not game:
            logger.warning(f"Игра {game_id} не найдена при отправке уведомлений")
            return
        
        # Подсчитываем статистику
        total_participants = len(game.participants)
        found_drivers = sum(1 for p in game.participants if p.role.value == 'driver' and p.is_found)
        total_drivers = sum(1 for p in game.participants if p.role.value == 'driver')
        
        logger.info(f"Участников в игре {game_id}: {total_participants}")
        
        duration = ""
        if game.started_at and game.ended_at:
            delta = game.ended_at - game.started_at
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            if hours > 0:
                duration = f"{hours}ч {minutes}м"
            else:
                duration = f"{minutes}м"
        
        completion_text = (
            f"🏁 <b>ИГРА ЗАВЕРШЕНА!</b>\n\n"
            f"🎮 <b>Игра:</b> {game.district}\n"
            f"⏰ <b>Продолжительность:</b> {duration}\n"
            f"🚗 <b>Найдено водителей:</b> {found_drivers}/{total_drivers}\n"
            f"👥 <b>Участников:</b> {total_participants}\n\n"
            f"🎉 Спасибо всем за участие!\n"
            f"Используйте /games для поиска новых игр."
        )
        
        # Отправляем уведомления всем участникам
        sent_count = 0
        for participant in game.participants:
            user, _ = UserService.get_user_by_id(participant.user_id)
            if user:
                try:
                    logger.info(f"Отправка уведомления о завершении игры участнику {user.telegram_id} ({user.name})")
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=completion_text,
                        parse_mode="HTML"
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления участнику {user.telegram_id}: {e}")
        
        logger.info(f"Отправлено {sent_count} уведомлений о завершении игры {game_id}")
                    
    except Exception as e:
        logger.error(f"Ошибка уведомления о завершении игры: {e}")

async def notify_drivers_about_found_inline(context: ContextTypes.DEFAULT_TYPE, game_id: int, seeker_name: str) -> None:
    """Уведомление водителей о том, что их нашли (для inline кнопок)"""
    try:
        from src.services.game_service import GameService
        from src.services.user_service import UserService
        
        game = GameService.get_game_by_id(game_id)
        if not game:
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
                                f"Если это правда, используйте кнопку '🚗 Меня нашли' в контекстном меню для подтверждения."
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления водителю {user.telegram_id}: {e}")
                        
    except Exception as e:
        logger.error(f"Ошибка уведомления водителей: {e}")

async def notify_participants_about_found_driver_inline(context: ContextTypes.DEFAULT_TYPE, game_id: int, driver_name: str) -> None:
    """Уведомление участников о найденном водителе (для inline кнопок)"""
    try:
        from src.services.game_service import GameService
        from src.services.user_service import UserService
        
        game = GameService.get_game_by_id(game_id)
        if not game:
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

async def check_game_completion_inline(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Проверка завершения игры (для inline кнопок)"""
    try:
        from src.services.game_service import GameService
        from src.models.game import GameStatus
        
        game = GameService.get_game_by_id(game_id)
        if not game or game.status not in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
            return
        
        # Проверяем, все ли водители найдены
        drivers_found = 0
        total_drivers = 0
        
        for participant in game.participants:
            if participant.role and participant.role.value == 'driver':
                total_drivers += 1
                if participant.is_found:
                    drivers_found += 1
        
        # Если все водители найдены, завершаем игру
        if drivers_found >= total_drivers and total_drivers > 0:
            GameService.end_game(game_id)
            await notify_game_completion_inline(context, game_id)
            
    except Exception as e:
        logger.error(f"Ошибка проверки завершения игры: {e}")

async def notify_game_completion_inline(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Уведомление о завершении игры (для inline кнопок)"""
    try:
        from src.services.game_service import GameService
        from src.services.user_service import UserService
        
        game = GameService.get_game_by_id(game_id)
        if not game:
            return
        
        # Подсчитываем статистику
        total_participants = len(game.participants)
        found_drivers = sum(1 for p in game.participants if p.role and p.role.value == 'driver' and p.is_found)
        total_drivers = sum(1 for p in game.participants if p.role and p.role.value == 'driver')
        
        duration = ""
        if game.started_at and game.ended_at:
            delta = game.ended_at - game.started_at
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            if hours > 0:
                duration = f"{hours}ч {minutes}м"
            else:
                duration = f"{minutes}м"
        
        completion_text = (
            f"🏁 <b>ИГРА ЗАВЕРШЕНА!</b>\n\n"
            f"🎮 <b>Игра:</b> {game.district}\n"
            f"⏰ <b>Продолжительность:</b> {duration}\n"
            f"🚗 <b>Найдено водителей:</b> {found_drivers}/{total_drivers}\n"
            f"👥 <b>Участников:</b> {total_participants}\n\n"
            f"🎉 Спасибо всем за участие!"
        )
        
        # Отправляем уведомления всем участникам
        for participant in game.participants:
            user, _ = UserService.get_user_by_id(participant.user_id)
            if user:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=completion_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления участнику {user.telegram_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Ошибка уведомления о завершении игры: {e}")

async def handle_game_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик возврата к основным настройкам игры"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.services.game_settings_service import GameSettingsService
    from src.keyboards.inline import get_game_settings_keyboard
    
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
    
    await query.edit_message_text(
        settings_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def handle_time_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик перехода к настройкам времени"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.services.game_settings_service import GameSettingsService
    from src.keyboards.inline import get_time_settings_keyboard
    
    settings = GameSettingsService.get_settings()
    keyboard = get_time_settings_keyboard(settings)
    
    time_text = (
        f"⏰ <b>Временные настройки</b>\n\n"
        f"🙈 <b>Фаза пряток:</b> {settings.hiding_phase_duration} минут\n"
        f"🔍 <b>Фаза поиска:</b> {settings.searching_phase_duration} минут\n"
        f"👥 <b>Мин. участников для старта:</b> {settings.min_participants_to_start}\n\n"
        f"💡 <i>Нажмите на настройку для изменения</i>"
    )
    
    await query.edit_message_text(
        time_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def handle_notification_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик перехода к настройкам уведомлений"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.services.game_settings_service import GameSettingsService
    from src.keyboards.inline import get_notification_settings_keyboard
    
    settings = GameSettingsService.get_settings()
    keyboard = get_notification_settings_keyboard(settings)
    
    notification_text = (
        f"🔔 <b>Настройки уведомлений</b>\n\n"
        f"{'✅' if settings.notify_on_role_assignment else '❌'} <b>Уведомления о назначении ролей</b>\n"
        f"Отправлять уведомление при назначении роли участнику\n\n"
        f"{'✅' if settings.notify_on_phase_change else '❌'} <b>Уведомления о смене фаз</b>\n"
        f"Отправлять уведомление при переходе между фазами игры\n\n"
        f"{'✅' if settings.notify_on_participant_action else '❌'} <b>Уведомления о действиях участников</b>\n"
        f"Отправлять уведомление о важных действиях участников\n\n"
        f"💡 <i>Нажмите на настройку для изменения</i>"
    )
    
    await query.edit_message_text(
        notification_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def handle_toggle_setting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик переключения настроек"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.services.game_settings_service import GameSettingsService
    
    # Маппинг callback'ов на поля настроек
    setting_map = {
        "toggle_auto_start_game": "auto_start_game",
        "toggle_auto_assign_roles": "auto_assign_roles",
        "toggle_auto_start_hiding": "auto_start_hiding", 
        "toggle_auto_start_searching": "auto_start_searching",
        "toggle_auto_end_game": "auto_end_game",
        "toggle_manual_control": "manual_control_mode",
        "toggle_notify_role": "notify_on_role_assignment",
        "toggle_notify_phase": "notify_on_phase_change",
        "toggle_notify_action": "notify_on_participant_action"
    }
    
    setting_name = setting_map.get(query.data)
    if not setting_name:
        await query.answer("❌ Неизвестная настройка", show_alert=True)
        return
    
    settings = GameSettingsService.get_settings()
    current_value = getattr(settings, setting_name)
    new_value = not current_value
    
    success = GameSettingsService.update_settings(**{setting_name: new_value})
    
    if success:
        # Возвращаемся к соответствующему меню
        if query.data.startswith("toggle_notify"):
            await handle_notification_settings_callback(update, context)
        elif query.data in ["toggle_manual_control"]:
            await handle_game_settings_callback(update, context)
        else:
            await handle_automation_settings_callback(update, context)
    else:
        await query.answer("❌ Ошибка при изменении настроек", show_alert=True)

async def handle_automation_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик настроек автоматизации"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.services.game_settings_service import GameSettingsService
    from src.keyboards.inline import get_automation_settings_keyboard
    
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

async def handle_time_value_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик изменения временных значений"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.services.game_settings_service import GameSettingsService
    
    # Парсим callback data
    data = query.data
    
    if data.startswith("set_hiding_time_"):
        field = "hiding_phase_duration"
        value = int(data.replace("set_hiding_time_", ""))
    elif data.startswith("set_searching_time_"):
        field = "searching_phase_duration"
        value = int(data.replace("set_searching_time_", ""))
    elif data.startswith("set_notification_time_"):
        field = "game_start_notification_time"
        value = int(data.replace("set_notification_time_", ""))
    elif data.startswith("set_min_participants_"):
        field = "min_participants_to_start"
        value = int(data.replace("set_min_participants_", ""))
    else:
        await query.answer("❌ Неизвестная настройка", show_alert=True)
        return
    
    success = GameSettingsService.update_settings(**{field: value})
    
    if success:
        await handle_time_settings_callback(update, context)
    else:
        await query.answer("❌ Ошибка при изменении настроек", show_alert=True)

async def handle_time_setting_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора конкретной временной настройки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.services.game_settings_service import GameSettingsService
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    settings = GameSettingsService.get_settings()
    data = query.data
    
    if data == "set_hiding_duration":
        setting_name = "hiding_phase_duration"
        title = "⏰ Длительность фазы пряток"
        current_value = settings.hiding_phase_duration
        options = [5, 10, 15, 20, 30, 45, 60]
        callback_prefix = "set_hiding_time_"
    elif data == "set_searching_duration":
        setting_name = "searching_phase_duration"
        title = "⏰ Длительность фазы поиска"
        current_value = settings.searching_phase_duration
        options = [30, 45, 60, 90, 120, 180, 240]
        callback_prefix = "set_searching_time_"
    elif data == "set_notification_time":
        setting_name = "game_start_notification_time"
        title = "🔔 Время уведомления о старте"
        current_value = settings.game_start_notification_time
        options = [5, 10, 15, 30, 60]
        callback_prefix = "set_notification_time_"
    elif data == "set_min_participants":
        setting_name = "min_participants_to_start"
        title = "👥 Минимум участников для старта"
        current_value = settings.min_participants_to_start
        options = [2, 3, 4, 5, 6, 8, 10]
        callback_prefix = "set_min_participants_"
    else:
        await query.answer("❌ Неизвестная настройка", show_alert=True)
        return
    
    # Создаем клавиатуру с вариантами
    buttons = []
    for option in options:
        marker = "✅" if option == current_value else ""
        button_text = f"{marker} {option}" + (" мин" if "time" in data or "duration" in data else "")
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"{callback_prefix}{option}"
        )])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="time_settings")])
    
    text = f"{title}\n\nТекущее значение: {current_value}\nВыберите новое значение:"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )

async def handle_reset_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик сброса настроек к умолчанию"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.services.game_settings_service import GameSettingsService
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Показываем диалог подтверждения
    confirmation_text = (
        f"⚠️ <b>Сброс настроек к умолчанию</b>\n\n"
        f"Вы уверены, что хотите сбросить все настройки игры к значениям по умолчанию?\n\n"
        f"<b>Будут сброшены:</b>\n"
        f"• Все настройки автоматизации\n"
        f"• Временные настройки\n"
        f"• Настройки уведомлений\n"
        f"• Режим управления\n\n"
        f"<i>Это действие нельзя отменить!</i>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, сбросить", callback_data="confirm_reset_settings"),
            InlineKeyboardButton("❌ Отменить", callback_data="game_settings")
        ]
    ])
    
    await query.edit_message_text(
        confirmation_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def handle_confirm_reset_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик подтверждения сброса настроек"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.services.game_settings_service import GameSettingsService
    
    # Сбрасываем настройки
    success = GameSettingsService.reset_to_defaults()
    
    if success:
        await query.answer("✅ Настройки сброшены к умолчанию!", show_alert=True)
    else:
        await query.answer("❌ Ошибка сброса настроек", show_alert=True)
    
    await handle_game_settings_callback(update, context)

async def handle_back_to_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик возврата в главное админское меню"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return
    
    from src.keyboards.reply import get_admin_keyboard
    
    admin_text = (
        f"🔑 <b>Админ-панель</b>\n\n"
        f"Добро пожаловать в админ-панель!\n"
        f"Выберите действие из меню ниже или используйте команды:\n\n"
        f"🎮 /admin_games - Управление играми\n"
        f"⚙️ /game_settings - Настройки игры\n"
        f"🗺 /manage_districts - Управление районами\n"
        f"👥 /manage_roles - Управление ролями\n"
        f"📋 /edit_rules - Редактирование правил\n"
        f"🌍 /zone_admin - Управление зонами\n"
        f"⏰ /scheduler_admin - Управление расписанием"
    )
    
    await query.edit_message_text(
        admin_text,
        parse_mode="HTML"
    )

def get_callback_handler_patterns():
    """Возвращает все паттерны для регистрации обработчиков"""

# Создаем обработчик
callback_handler = CallbackQueryHandler(handle_callback) 