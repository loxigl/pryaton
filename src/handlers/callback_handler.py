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
from src.handlers.photo import handle_photo_approval
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
            await handle_photo_approval(update, context)
        
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
                f"• Найдите укромное место для прятки\n"
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
                f"• Сделайте фото своего места прятки\n"
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
        
        user, _ = UserService.get_user_by_telegram_id(user_id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return
        
        participant = next(
            (p for p in game.participants if p.user_id == user.id),
            None
        )
        
        if not participant or participant.role.value != 'seeker':
            await query.edit_message_text("❌ Эта функция доступна только искателям")
            return
        
        # Отмечаем участника как нашедшего
        participant.is_found = True
        participant.found_at = datetime.now()
        
        # Сохраняем изменения
        from src.models.base import get_db
        db_generator = get_db()
        db = next(db_generator)
        db.commit()
        
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
        
        # Отмечаем водителя как найденного
        participant.is_found = True
        participant.found_at = datetime.now()
        
        # Сохраняем изменения
        from src.models.base import get_db
        db_generator = get_db()
        db = next(db_generator)
        db.commit()
        
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
    """Обработчик callback'а 'Меня нашли' (водитель)"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🚗 <b>Вас нашли!</b>\n\n"
        "Поздравляем! Искатели успешно обнаружили ваше местоположение.\n"
        "Функция завершения игры будет реализована в следующих обновлениях.",
        parse_mode="HTML"
    )

async def handle_found_seeker_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а 'Нашел водителя' (искатель)"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔍 <b>Водитель найден!</b>\n\n"
        "Отлично! Вы нашли спрятавшегося водителя.\n"
        "Функция завершения игры будет реализована в следующих обновлениях.",
        parse_mode="HTML"
    )

async def handle_photo_place_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а фото места (водитель)"""
    query = update.callback_query
    await query.answer()
    
    from src.keyboards.reply import get_photo_action_keyboard
    
    await query.edit_message_text(
        "📸 <b>Фото места</b>\n\n"
        "Сделайте фотографию вашего местоположения для подтверждения:",
        parse_mode="HTML",
        reply_markup=get_photo_action_keyboard()
    )

async def handle_photo_find_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'а фото находки (искатель)"""
    query = update.callback_query
    await query.answer()
    
    from src.keyboards.reply import get_photo_action_keyboard
    
    await query.edit_message_text(
        "📸 <b>Фото находки</b>\n\n"
        "Сделайте фотографию найденного места или водителя:",
        parse_mode="HTML",
        reply_markup=get_photo_action_keyboard()
    )

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
                "• Найдите укромное место для прятки\n"
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
        'in_progress': '🔥 В процессе',
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
        
        game = GameService.get_game_by_id(game_id)
        if not game or game.status != GameStatus.IN_PROGRESS:
            return
        
        # Проверяем, все ли водители найдены
        drivers_found = 0
        total_drivers = 0
        
        for participant in game.participants:
            if participant.role.value == 'driver':
                total_drivers += 1
                if participant.is_found:
                    drivers_found += 1
        
        # Если все водители найдены, завершаем игру
        if drivers_found >= total_drivers and total_drivers > 0:
            game.status = GameStatus.COMPLETED
            game.ended_at = datetime.now()
            
            # Сохраняем изменения
            from src.models.base import get_db
            db_generator = get_db()
            db = next(db_generator)
            db.commit()
            
            # Уведомляем всех участников о завершении игры
            await notify_game_completion_callback(context, game_id)
            
    except Exception as e:
        logger.error(f"Ошибка проверки завершения игры: {e}")

async def notify_game_completion_callback(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Уведомление участников о завершении игры"""
    try:
        from src.services.game_service import GameService
        
        game = GameService.get_game_by_id(game_id)
        if not game:
            return
        
        # Подсчитываем статистику
        total_participants = len(game.participants)
        found_drivers = sum(1 for p in game.participants if p.role.value == 'driver' and p.is_found)
        total_drivers = sum(1 for p in game.participants if p.role.value == 'driver')
        
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

def get_callback_handler_patterns():
    """Возвращает все паттерны для регистрации обработчиков"""

# Создаем обработчик
callback_handler = CallbackQueryHandler(handle_callback) 