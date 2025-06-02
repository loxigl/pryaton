from telegram import Update, File, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from loguru import logger
from datetime import datetime
import os
import uuid

from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.photo_service import PhotoService
from src.models.game import GameStatus, GameRole
from src.keyboards.reply import get_contextual_main_keyboard

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
            reply_markup=get_contextual_main_keyboard(UserService.is_admin(user_id))
        )
        return
    
    # Проверяем, что пользователь - искатель в какой-то из активных игр
    seeker_games = []
    for game in active_games:
        if game.status == GameStatus.IN_PROGRESS:
            # Проверяем роль пользователя в игре
            participant = next(
                (p for p in game.participants if p.user_id == user.id),
                None
            )
            if participant and participant.role == GameRole.SEEKER:
                seeker_games.append(game)
    
    if not seeker_games:
        await update.message.reply_text(
            "Вы не являетесь искателем в активных играх. Только искатели могут отправлять фотографии.",
            reply_markup=get_contextual_main_keyboard(UserService.is_admin(user_id))
        )
        return
    
    # Берем наибольшее фото для лучшего качества
    photo = update.message.photo[-1]
    photo_file_id = photo.file_id
    
    logger.info(f"Получена фотография от пользователя {user_id}: {photo_file_id}")
    
    # Сохраняем фотографию для всех активных игр, где пользователь - искатель
    saved_count = 0
    for game in seeker_games:
        if PhotoService.save_user_photo(user.id, game.id, photo_file_id):
            saved_count += 1
    
    if saved_count > 0:
        success_text = (
            f"📸 <b>Фотография получена!</b>\n\n"
            f"✅ Сохранено для игр: {saved_count}\n\n"
            f"Ваша фотография отправлена на проверку водителям.\n"
            f"Дождитесь подтверждения или отклонения."
        )
        
        await update.message.reply_text(
            success_text,
            reply_markup=get_contextual_main_keyboard(UserService.is_admin(user_id)),
            parse_mode="HTML"
        )
        
        # Уведомляем водителей в каждой игре
        for game in seeker_games:
            await notify_drivers_about_photo(context, game.id, user.name, photo_file_id)
    else:
        await update.message.reply_text(
            "❌ Не удалось сохранить фотографию. Попробуйте еще раз.",
            reply_markup=get_contextual_main_keyboard(UserService.is_admin(user_id))
        )

async def notify_drivers_about_photo(context: ContextTypes.DEFAULT_TYPE, game_id: int, seeker_name: str, photo_file_id: str) -> None:
    """Уведомление водителей о новой фотографии"""
    try:
        game = GameService.get_game_by_id(game_id)
        if not game:
            return
        
        # Находим всех водителей в игре
        drivers = []
        for participant in game.participants:
            if participant.role == GameRole.DRIVER:
                # Получаем пользователя для получения telegram_id
                user, _ = UserService.get_user_by_id(participant.user_id)
                if user:
                    drivers.append(user)
        
        # Отправляем уведомления водителям
        for driver in drivers:
            try:
                # Создаем клавиатуру для подтверждения/отклонения
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"photo_approve_{game_id}_{photo_file_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"photo_reject_{game_id}_{photo_file_id}")
                    ]
                ])
                
                notification_text = (
                    f"📸 <b>Новая фотография для проверки!</b>\n\n"
                    f"🎮 <b>Игра:</b> {game.district}\n"
                    f"👤 <b>От игрока:</b> {seeker_name}\n\n"
                    f"Подтвердите или отклоните фотографию:"
                )
                
                await context.bot.send_photo(
                    chat_id=driver.telegram_id,
                    photo=photo_file_id,
                    caption=notification_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления водителю {driver.telegram_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка уведомления водителей: {e}")

async def handle_photo_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик подтверждения фотографии водителем"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Парсим callback data
    data_parts = query.data.split('_')
    if len(data_parts) < 4:
        await query.edit_message_text("❌ Ошибка в данных запроса.")
        return
    
    action = data_parts[1]  # approve или reject
    game_id = int(data_parts[2])
    photo_file_id = '_'.join(data_parts[3:])  # Собираем обратно file_id
    
    # Получаем пользователя-водителя
    user, _ = UserService.get_user_by_telegram_id(user_id)
    if not user:
        await query.edit_message_text("❌ Пользователь не найден в системе.")
        return
    
    # Проверяем, что пользователь действительно водитель в этой игре
    game = GameService.get_game_by_id(game_id)
    if not game:
        await query.edit_message_text("❌ Игра не найдена.")
        return
    
    participant = next(
        (p for p in game.participants if p.user_id == user.id),
        None
    )
    
    if not participant or participant.role != GameRole.DRIVER:
        await query.edit_message_text("❌ Вы не являетесь водителем в этой игре.")
        return
    
    # Обрабатываем действие
    if action == "approve":
        # Подтверждаем фотографию
        success = PhotoService.approve_photo(photo_file_id, user.id)
        if success:
            await query.edit_message_text(
                f"✅ <b>Фотография подтверждена!</b>\n\n"
                f"Игрок успешно вас нашел.",
                parse_mode="HTML"
            )
            
            # Уведомляем искателя об успехе
            await notify_seeker_about_approval(context, game_id, photo_file_id, True)
            
            # Помечаем участника как найденного
            # Здесь нужно найти ID искателя по фотографии
            seeker_id = PhotoService.get_photo_seeker_id(photo_file_id)
            if seeker_id:
                GameService.mark_participant_found(game_id, seeker_id)
                
                # Проверяем, не закончилась ли игра
                await check_game_completion(context, game_id)
        else:
            await query.edit_message_text("❌ Ошибка при подтверждении фотографии.")
            
    elif action == "reject":
        # Отклоняем фотографию
        success = PhotoService.reject_photo(photo_file_id, user.id)
        if success:
            await query.edit_message_text(
                f"❌ <b>Фотография отклонена</b>\n\n"
                f"Игрок должен продолжить поиски.",
                parse_mode="HTML"
            )
            
            # Уведомляем искателя об отклонении
            await notify_seeker_about_approval(context, game_id, photo_file_id, False)
        else:
            await query.edit_message_text("❌ Ошибка при отклонении фотографии.")

async def notify_seeker_about_approval(context: ContextTypes.DEFAULT_TYPE, game_id: int, photo_file_id: str, approved: bool) -> None:
    """Уведомление искателя о результате проверки фотографии"""
    try:
        # Получаем информацию о фотографии и искателе
        seeker_id = PhotoService.get_photo_seeker_id(photo_file_id)
        if not seeker_id:
            return
        
        user, _ = UserService.get_user_by_id(seeker_id)
        if not user:
            return
        
        game = GameService.get_game_by_id(game_id)
        if not game:
            return
        
        if approved:
            text = (
                f"🎉 <b>Поздравляем!</b>\n\n"
                f"✅ Ваша фотография подтверждена водителем!\n"
                f"🎮 <b>Игра:</b> {game.district}\n\n"
                f"Вы успешно нашли машину!"
            )
        else:
            text = (
                f"❌ <b>Фотография отклонена</b>\n\n"
                f"🎮 <b>Игра:</b> {game.district}\n\n"
                f"Продолжайте поиски! Возможно, это не та машина или фото нечеткое."
            )
        
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка уведомления искателя: {e}")

async def check_game_completion(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Проверка завершения игры"""
    try:
        game = GameService.get_game_by_id(game_id)
        if not game or game.status != GameStatus.IN_PROGRESS:
            return
        
        # Проверяем, все ли водители найдены
        drivers_found = 0
        total_drivers = 0
        
        for participant in game.participants:
            if participant.role == GameRole.DRIVER:
                total_drivers += 1
                if participant.is_found:
                    drivers_found += 1
        
        # Если все водители найдены, завершаем игру
        if drivers_found >= total_drivers and total_drivers > 0:
            GameService.end_game(game_id)
            
            # Уведомляем всех участников о завершении игры
            await notify_game_completion(context, game_id)
            
    except Exception as e:
        logger.error(f"Ошибка проверки завершения игры: {e}")

async def notify_game_completion(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Уведомление участников о завершении игры"""
    try:
        game = GameService.get_game_by_id(game_id)
        if not game:
            return
        
        completion_text = (
            f"🏁 <b>Игра завершена!</b>\n\n"
            f"🎮 <b>Игра:</b> {game.district}\n"
            f"⏰ <b>Время игры:</b> {game.started_at.strftime('%d.%m %H:%M')} - {datetime.now().strftime('%H:%M')}\n\n"
            f"🎉 Все водители найдены! Спасибо за участие!"
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

# Создаем обработчики
photo_handlers = [
    MessageHandler(filters.PHOTO, handle_photo),
    CallbackQueryHandler(handle_photo_approval, pattern=r"photo_(approve|reject)_\d+_.*"),
] 