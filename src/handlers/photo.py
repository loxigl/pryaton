import pytz
from telegram import Update, File, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from loguru import logger
from datetime import datetime, timezone
import os
import uuid

from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.photo_service import PhotoService
from src.models.game import GameStatus, GameRole, PhotoType
from src.keyboards.reply import get_contextual_main_keyboard

DEFAULT_TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "Europe/Moscow"))

def format_msk_time(dt: datetime) -> str:
    """Форматирует время в МСК"""
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%H:%M')

def format_msk_datetime(dt: datetime) -> str:
    """Форматирует дату и время в МСК"""
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%d.%m.%Y %H:%M')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик получения фотографии от пользователя"""
    user_id = update.effective_user.id
    
    if not update.message.photo:
        await update.message.reply_text("❌ Фотография не получена. Попробуйте еще раз.")
        return
    
    # Получаем пользователя
    user, _ = UserService.get_user_by_telegram_id(user_id)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден в системе.")
        return
    
    # Получаем активные игры пользователя
    active_games = GameService.get_user_active_games(user.id)
    
    if not active_games:
        await update.message.reply_text(
            "У вас нет активных игр для отправки фотографий.",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        return
    
    # Берем наибольшее фото для лучшего качества
    photo = update.message.photo[-1]
    photo_file_id = photo.file_id
    
    logger.info(f"Получена фотография от пользователя {user_id}: {photo_file_id}")
    
    # Ищем подходящие игры для отправки фото
    suitable_games = []
    for game in active_games:
        # Проверяем роль пользователя в игре
        participant = next(
            (p for p in game.participants if p.user_id == user.id),
            None
        )
        
        if not participant or not participant.role:
            continue
            
        # Водители могут отправлять фото в фазе пряток
        if (participant.role == GameRole.DRIVER and 
            game.status == GameStatus.HIDING_PHASE):
            suitable_games.append((game, PhotoType.HIDING_SPOT))
            
        # Искатели могут отправлять фото в фазе поиска
        elif (participant.role == GameRole.SEEKER and 
              game.status == GameStatus.SEARCHING_PHASE):
            suitable_games.append((game, PhotoType.FOUND_CAR))
    
    if not suitable_games:
        status_text = {
            GameStatus.UPCOMING: "Игра еще не началась",
            GameStatus.HIDING_PHASE: "Сейчас идет фаза пряток. Искатели не могут отправлять фото.",
            GameStatus.SEARCHING_PHASE: "Сейчас идет фаза поиска. Водители не могут отправлять фото.",
            GameStatus.COMPLETED: "Игра уже завершена",
            GameStatus.CANCELED: "Игра отменена"
        }
        
        current_status = active_games[0].status if active_games else None
        message = status_text.get(current_status, "Нет подходящих игр для отправки фото.")
        
        await update.message.reply_text(
            f"❌ {message}",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        return
    
    # Обрабатываем фото для каждой подходящей игры
    saved_count = 0
    for game, photo_type in suitable_games:
        if photo_type == PhotoType.HIDING_SPOT:
            # Проверяем, не отправил ли водитель уже фото
            participant = next(p for p in game.participants if p.user_id == user.id)
            if participant.has_hidden:
                await update.message.reply_text(
                    f"⚠️ Вы уже отправили фото места пряток для игры в районе {game.district}.",
                    reply_markup=get_contextual_main_keyboard(user_id)
                )
                continue
            
            # Сохраняем фото места пряток
            saved_photo = PhotoService.save_user_photo(
                user.id, game.id, photo_file_id, PhotoType.HIDING_SPOT,
                description="Фото места пряток"
            )
            
        elif photo_type == PhotoType.FOUND_CAR:
            # Для фото найденной машины нужно выбрать водителя
            await show_driver_selection(update, context, game, photo_file_id, user.id)
            return  # Выходим здесь, чтобы дождаться выбора водителя
        
        if saved_photo:
            saved_count += 1
            # Уведомляем админов о новом фото
            await notify_admins_about_photo(context, saved_photo)
    
    if saved_count > 0:
        if photo_type == PhotoType.HIDING_SPOT:
            success_text = (
                f"📸 <b>Фото места пряток получено!</b>\n\n"
                f"✅ Сохранено для игр: {saved_count}\n\n"
                f"Ваше фото отправлено администраторам на проверку.\n"
                f"Дождитесь подтверждения."
            )
        else:
            success_text = (
                f"📸 <b>Фото получено!</b>\n\n"
                f"✅ Сохранено для игр: {saved_count}\n\n"
                f"Ваше фото отправлено администраторам на проверку."
            )
        
        await update.message.reply_text(
            success_text,
            reply_markup=get_contextual_main_keyboard(user_id),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "❌ Не удалось сохранить фотографию. Попробуйте еще раз.",
            reply_markup=get_contextual_main_keyboard(user_id)
        )

async def show_driver_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               game, photo_file_id: str, seeker_id: int) -> None:
    """Показать выбор водителя для фото найденной машины"""
    # Получаем всех водителей в игре
    drivers = [p for p in game.participants if p.role == GameRole.DRIVER]
    
    if not drivers:
        await update.message.reply_text("❌ В игре нет водителей.")
        return
    
    # Создаем клавиатуру с водителями
    buttons = []
    for driver in drivers:
        # Получаем имя водителя
        user, _ = UserService.get_user_by_id(driver.user_id)
        driver_name = user.name if user else f"Водитель {driver.user_id}"
        
        # Добавляем статус (найден/не найден)
        status = "✅" if driver.is_found else "🔍"
        
        buttons.append([InlineKeyboardButton(
            f"{status} {driver_name}",
            callback_data=f"select_driver_{game.id}_{driver.user_id}_{seeker_id}"
        )])
    
    # Добавляем кнопку отмены
    buttons.append([InlineKeyboardButton("❌ Отменить", callback_data="cancel_driver_selection")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    # Сохраняем file_id в контексте пользователя для последующего использования
    if 'photo_temp' not in context.user_data:
        context.user_data['photo_temp'] = {}
    context.user_data['photo_temp'][f"{game.id}_{seeker_id}"] = photo_file_id
    
    await update.message.reply_text(
        f"🎯 <b>Выберите водителя, которого вы нашли:</b>\n\n"
        f"🎮 Игра: {game.district}\n"
        f"✅ - уже найден, 🔍 - еще ищется",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def handle_driver_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора водителя для фото"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_driver_selection":
        await query.edit_message_text("❌ Отправка фото отменена.")
        return
    
    # Парсим данные
    try:
        _, _, game_id, driver_id, seeker_id = query.data.split('_')
        game_id = int(game_id)
        driver_id = int(driver_id)
        seeker_id = int(seeker_id)
    except ValueError:
        await query.edit_message_text("❌ Ошибка в данных запроса.")
        return
    
    # Получаем file_id из контекста
    photo_file_id = context.user_data.get('photo_temp', {}).get(f"{game_id}_{seeker_id}")
    if not photo_file_id:
        await query.edit_message_text("❌ Фото не найдено. Попробуйте отправить заново.")
        return
    
    # Получаем информацию о водителе
    driver_user, _ = UserService.get_user_by_id(driver_id)
    driver_name = driver_user.name if driver_user else f"Водитель {driver_id}"
    
    # Сохраняем фото с указанием найденного водителя
    saved_photo = PhotoService.save_user_photo(
        seeker_id, game_id, photo_file_id, PhotoType.FOUND_CAR,
        description=f"Фото найденной машины водителя {driver_name}",
        found_driver_id=driver_id
    )
    
    if saved_photo:
        await query.edit_message_text(
            f"✅ <b>Фото найденной машины отправлено!</b>\n\n"
            f"🎯 Найденный водитель: {driver_name}\n"
            f"📸 Фото отправлено администраторам на проверку.",
            parse_mode="HTML"
        )
        
        # Уведомляем админов
        await notify_admins_about_photo(context, saved_photo)
        
        # Очищаем временные данные
        if 'photo_temp' in context.user_data:
            context.user_data['photo_temp'].pop(f"{game_id}_{seeker_id}", None)
    else:
        await query.edit_message_text("❌ Не удалось сохранить фото. Попробуйте еще раз.")

async def notify_admins_about_photo(context: ContextTypes.DEFAULT_TYPE, photo) -> None:
    """Уведомление администраторов о новой фотографии"""
    try:
        # Получаем список админов
        admins = UserService.get_admin_users()
        
        if not admins:
            logger.warning("Нет администраторов для уведомления о фото")
            return
        
        # Получаем информацию об игре и пользователе
        game = GameService.get_game_by_id(photo.game_id)
        user, _ = UserService.get_user_by_id(photo.user_id)
        
        if not game or not user:
            logger.error(f"Не удалось получить данные для фото {photo.id}")
            return
        
        # Формируем текст уведомления
        photo_type_text = {
            PhotoType.HIDING_SPOT: "📍 Фото места пряток",
            PhotoType.FOUND_CAR: "🎯 Фото найденной машины"
        }
        
        caption_text = (
            f"📸 <b>Новое фото для проверки!</b>\n\n"
            f"{photo_type_text.get(photo.photo_type, 'Фото')}\n"
            f"🎮 <b>Игра:</b> {game.district}\n"
            f"👤 <b>От:</b> {user.name}\n"
            f"📅 <b>Время:</b> {format_msk_datetime(photo.uploaded_at)}\n"
        )
        
        if photo.photo_type == PhotoType.FOUND_CAR and photo.found_driver_id:
            found_driver, _ = UserService.get_user_by_id(photo.found_driver_id)
            driver_name = found_driver.name if found_driver else f"ID {photo.found_driver_id}"
            caption_text += f"🎯 <b>Найденный водитель:</b> {driver_name}\n"
        
        caption_text += f"\n📝 <b>Описание:</b> {photo.description or 'Нет'}"
        
        # Создаем клавиатуру для админа
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin_approve_photo_{photo.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_photo_{photo.id}")
            ],
            [InlineKeyboardButton("📋 Статистика игры", callback_data=f"admin_game_stats_{game.id}")]
        ])
        
        # Отправляем уведомления всем админам
        for admin in admins:
            try:
                await context.bot.send_photo(
                    chat_id=admin.telegram_id,
                    photo=photo.file_id,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin.telegram_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка уведомления админов о фото: {e}")

async def handle_admin_photo_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик подтверждения/отклонения фото администратором"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем права администратора
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав для выполнения этого действия.")
        return
    
    # Парсим данные
    try:
        if query.data.startswith("admin_approve_photo_"):
            action = "approve"
            photo_id = int(query.data.replace("admin_approve_photo_", ""))
        elif query.data.startswith("admin_reject_photo_"):
            action = "reject"
            photo_id = int(query.data.replace("admin_reject_photo_", ""))
        else:
            await query.edit_message_text("❌ Неизвестное действие.")
            return
    except ValueError:
        await query.edit_message_text("❌ Ошибка в данных запроса.")
        return
    
    # Получаем фото
    photo = PhotoService.get_photo_by_id(photo_id)
    if not photo:
        await query.edit_message_text("❌ Фотография не найдена.")
        return
    
    # Получаем админа
    admin, _ = UserService.get_user_by_telegram_id(user_id)
    if not admin:
        await query.edit_message_text("❌ Администратор не найден в системе.")
        return
    
    # Выполняем действие
    if action == "approve":
        success = PhotoService.approve_photo(photo_id, admin.id)
        if success:
            await query.edit_message_caption(
                caption=(
                    f"✅ <b>Фотография подтверждена!</b>\n\n"
                    f"📸 ID: {photo_id}\n"
                    f"👤 Администратор: {admin.name}"
                ),
                parse_mode="HTML"
            )
            try:
                # Обрабатываем в зависимости от типа фото
                if photo.photo_type == PhotoType.HIDING_SPOT:
                    # Для фото места пряток - обновляем статус спрятанности водителя
                    GameService.update_participant_hidden_status(photo.game_id, photo.user_id, True)
                elif photo.photo_type == PhotoType.FOUND_CAR and photo.found_driver_id:
                    # Для фото найденной машины - отмечаем водителя как найденного
                    GameService.mark_participant_found(photo.game_id, photo.found_driver_id)
                    
                    # Получаем имя искателя для уведомления
                    seeker, _ = UserService.get_user_by_id(photo.user_id)
                    seeker_name = seeker.name if seeker else f"ID {photo.user_id}"
                    
                    # Уведомляем водителя что его нашли
                    from src.handlers.callback_handler import notify_drivers_about_found
                    await notify_drivers_about_found(context, photo.game_id, seeker_name)
                    
                    # Проверяем завершение игры
                    from src.handlers.callback_handler import check_game_completion_callback
                    await check_game_completion_callback(context, photo.game_id)
            except Exception as e:
                logger.error(f"Ошибка при обработке подтвержденного фото: {e}")
                
            
            # Уведомляем пользователя об одобрении
            await notify_user_about_photo_result(context, photo, True, admin.name)
            
        else:
            await query.edit_message_caption(
                caption="❌ Не удалось подтвердить фотографию.",
                parse_mode="HTML"
            )
    
    elif action == "reject":
        success = PhotoService.reject_photo(photo_id, admin.id, "Отклонено администратором")
        if success:
            await query.edit_message_caption(
                caption=(
                    f"❌ <b>Фотография отклонена!</b>\n\n"
                    f"📸 ID: {photo_id}\n"
                    f"👤 Администратор: {admin.name}"
                ),
                parse_mode="HTML"
            )
            
            # Уведомляем пользователя об отклонении
            await notify_user_about_photo_result(context, photo, False, admin.name)
            
        else:
            await query.edit_message_caption(
                caption="❌ Не удалось отклонить фотографию.",
                parse_mode="HTML"
            )

async def notify_user_about_photo_result(context: ContextTypes.DEFAULT_TYPE, 
                                       photo, approved: bool, admin_name: str) -> None:
    """Уведомление пользователя о результате проверки фото"""
    try:
        user, _ = UserService.get_user_by_id(photo.user_id)
        if not user:
            return
        
        game = GameService.get_game_by_id(photo.game_id)
        if not game:
            return
        
        if approved:
            if photo.photo_type == PhotoType.HIDING_SPOT:
                text = (
                    f"✅ <b>Ваше фото места пряток подтверждено!</b>\n\n"
                    f"🎮 Игра: {game.district}\n"
                    f"👤 Подтвердил: {admin_name}\n\n"
                    f"Отлично! Теперь ждите начала фазы поиска."
                )
            else:
                found_driver_text = ""
                if photo.found_driver_id:
                    found_driver, _ = UserService.get_user_by_id(photo.found_driver_id)
                    if found_driver:
                        found_driver_text = f"\n🎯 Найденный водитель: {found_driver.name}"
                
                text = (
                    f"✅ <b>Ваше фото найденной машины подтверждено!</b>\n\n"
                    f"🎮 Игра: {game.district}{found_driver_text}\n"
                    f"👤 Подтвердил: {admin_name}\n\n"
                    f"Отличная работа! Продолжайте поиск."
                )
        else:
            text = (
                f"❌ <b>Ваше фото отклонено</b>\n\n"
                f"🎮 Игра: {game.district}\n"
                f"👤 Отклонил: {admin_name}\n\n"
                f"Попробуйте отправить более четкое фото."
            )
        
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя о результате: {e}")

async def handle_admin_game_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик показа статистики игры для админа"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем права администратора
    if not UserService.is_admin(user_id):
        await query.edit_message_text("❌ У вас нет прав для выполнения этого действия.")
        return
    
    # Парсим game_id
    try:
        game_id = int(query.data.replace("admin_game_stats_", ""))
    except ValueError:
        await query.edit_message_text("❌ Ошибка в данных запроса.")
        return
    
    # Получаем статистику
    game = GameService.get_game_by_id(game_id)
    if not game:
        await query.edit_message_text("❌ Игра не найдена.")
        return
    
    hiding_stats = GameService.get_hiding_stats(game_id)
    photo_stats = PhotoService.get_hiding_photos_stats(game_id)
    
    stats_text = (
        f"📊 <b>Статистика игры #{game_id}</b>\n\n"
        f"🎮 <b>Район:</b> {game.district}\n"
        f"📅 <b>Статус:</b> {game.status.value}\n\n"
        f"🚗 <b>Водители:</b> {hiding_stats['total_drivers']}\n"
        f"✅ Спрятались: {hiding_stats['hidden_count']}\n"
        f"⏳ Не спрятались: {hiding_stats['not_hidden_count']}\n\n"
        f"📸 <b>Фото мест пряток:</b>\n"
        f"📤 Всего: {photo_stats.get('photos_count', 0)}\n"
        f"✅ Подтверждено: {photo_stats.get('approved_photos', 0)}\n"
        f"⏳ Ожидают: {photo_stats.get('pending_photos', 0)}\n"
        f"❌ Отклонено: {photo_stats.get('rejected_photos', 0)}\n"
    )
    
    if hiding_stats['not_hidden_count'] > 0:
        not_hidden_names = []
        for driver in hiding_stats['not_hidden_drivers']:
            user, _ = UserService.get_user_by_id(driver.user_id)
            name = user.name if user else f"ID {driver.user_id}"
            not_hidden_names.append(name)
        
        stats_text += f"\n⚠️ <b>Не спрятались:</b>\n" + "\n".join(f"• {name}" for name in not_hidden_names)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data=f"admin_game_stats_{game_id}")]
    ])
    
    await query.edit_message_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )



# Регистрация обработчиков
photo_handlers = [
    MessageHandler(filters.PHOTO, handle_photo),
    CallbackQueryHandler(handle_driver_selection, pattern=r"^select_driver_\d+_\d+_\d+$"),
    CallbackQueryHandler(handle_driver_selection, pattern="^cancel_driver_selection$"),
    CallbackQueryHandler(handle_admin_photo_approval, pattern=r"^admin_approve_photo_\d+$"),
    CallbackQueryHandler(handle_admin_photo_approval, pattern=r"^admin_reject_photo_\d+$"),
    CallbackQueryHandler(handle_admin_game_stats, pattern=r"^admin_game_stats_\d+$"),
] 