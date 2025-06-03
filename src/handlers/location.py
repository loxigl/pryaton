from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from loguru import logger
from datetime import datetime
import os

from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.location_service import LocationService
from src.models.game import GameStatus
from src.keyboards.reply import get_contextual_main_keyboard

async def request_location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запрос геолокации у пользователя для участия в игре"""
    user_id = update.effective_user.id
    
    # Получаем пользователя
    user, _ = UserService.get_user_by_telegram_id(user_id)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден в системе.")
        return
    
    # Проверяем, есть ли у пользователя активные игры
    active_games = GameService.get_user_active_games(user.id)
    
    if not active_games:
        await update.message.reply_text(
            "У вас нет активных игр, требующих отправки геолокации.",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        return
    
    # Создаем клавиатуру для отправки геолокации
    location_button = KeyboardButton(text="📍 Отправить мою геолокацию", request_location=True)
    back_button = KeyboardButton(text="🏠 Главное меню")
    keyboard = ReplyKeyboardMarkup([[location_button], [back_button]], resize_keyboard=True)
    
    location_text = (
        f"📍 <b>Отправка геолокации</b>\n\n"
        f"Для участия в игре необходимо отправить вашу текущую геолокацию.\n\n"
        f"<b>Активные игры:</b>\n"
    )
    
    for game in active_games:
        location_text += f"• {game.district}, {game.scheduled_at.strftime('%d.%m %H:%M')}\n"
    
    location_text += f"\n📱 Нажмите кнопку ниже для отправки геолокации:"
    
    await update.message.reply_text(
        location_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик получения геолокации от пользователя"""
    user_id = update.effective_user.id
    
    if not update.message.location:
        await update.message.reply_text("❌ Геолокация не получена. Попробуйте еще раз.")
        return
    
    location = update.message.location
    latitude = location.latitude
    longitude = location.longitude
    
    logger.info(f"Получена геолокация от пользователя {user_id}: {latitude}, {longitude}")

    # Получаем пользователя
    user, _ = UserService.get_user_by_telegram_id(user_id)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден в системе.")
        return
    
    # Получаем активные игры пользователя
    active_games = GameService.get_user_active_games(user.id)
    
    if not active_games:
        await update.message.reply_text(
            "У вас нет активных игр.",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        return
    
    # Сохраняем геолокацию для всех активных игр
    saved_count = 0
    for game in active_games:
        if LocationService.save_user_location(user.id, game.id, latitude, longitude):
            saved_count += 1
            
            # Уведомляем админов о получении геолокации
            await notify_admins_about_location(context, user, game, latitude, longitude)
    
    if saved_count > 0:
        # Проверяем, находится ли пользователь в игровой зоне
        in_zone_games = []
        out_zone_games = []
        
        for game in active_games:
            # Используем улучшенную проверку зоны
            if LocationService.is_user_in_game_zone(user.id, game.id):
                in_zone_games.append(game)
            else:
                out_zone_games.append(game)
        
        success_text = f"✅ <b>Геолокация сохранена!</b>\n\n"
        success_text += f"📍 Координаты: {latitude:.6f}, {longitude:.6f}\n"
        success_text += f"🎮 Обновлено игр: {saved_count}\n\n"
        
        if in_zone_games:
            success_text += f"🟢 <b>Вы в игровой зоне:</b>\n"
            for game in in_zone_games:
                zone_info = ""
                if game.has_game_zone:
                    zone_info = f" (радиус {game.zone_radius}м)"
                success_text += f"• {game.district}{zone_info}\n"
            
            if out_zone_games:
                success_text += f"\n🟡 <b>Вне игровой зоны:</b>\n"
                for game in out_zone_games:
                    zone_info = ""
                    if game.has_game_zone:
                        zone_info = f" (радиус {game.zone_radius}м)"
                    success_text += f"• {game.district}{zone_info}\n"
                success_text += f"Приближайтесь к зоне игры для участия."
        else:
            success_text += f"🟡 <b>Вы пока не в игровых зонах</b>\n"
            success_text += f"Приближайтесь к местам игр для участия."
        
        await update.message.reply_text(
            success_text,
            reply_markup=get_contextual_main_keyboard(user_id),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "❌ Не удалось сохранить геолокацию. Попробуйте еще раз.",
            reply_markup=get_contextual_main_keyboard(user_id)
        )

async def show_game_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать карту игры с участниками (для админов)"""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id
    
    # Проверяем права администратора
    if not UserService.is_admin(user_id):
        text = "❌ Доступ запрещен. Только для администраторов."
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    
    # Получаем ID игры
    game_id = None
    if context.args and len(context.args) > 0:
        try:
            game_id = int(context.args[0])
        except ValueError:
            pass
    
    if not game_id:
        text = "❌ Не указан ID игры."
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    
    # Получаем игру
    game = GameService.get_game_by_id(game_id)
    if not game:
        text = "❌ Игра не найдена."
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    
    # Получаем геолокации участников
    participants_locations = LocationService.get_game_participants_locations(game_id)
    
    map_text = (
        f"🗺 <b>Карта игры #{game_id}</b>\n\n"
        f"📍 <b>Район:</b> {game.district}\n"
        f"⏰ <b>Время:</b> {game.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🚦 <b>Статус:</b> {game.status.value}\n\n"
        f"👥 <b>Участники с геолокацией:</b>\n"
    )
    
    if participants_locations:
        for i, (user_info, location) in enumerate(participants_locations, 1):
            map_text += (
                f"{i}. {user_info.name} ({user_info.default_role.value})\n"
                f"   📍 {location.latitude:.6f}, {location.longitude:.6f}\n"
                f"   🕐 {location.created_at.strftime('%H:%M:%S')}\n\n"
            )
    else:
        map_text += "Пока нет участников с геолокацией.\n"
    
    if query:
        await query.edit_message_text(map_text, parse_mode="HTML")
    else:
        await update.message.reply_text(map_text, parse_mode="HTML")

async def notify_admins_about_location(context: ContextTypes.DEFAULT_TYPE, user, game, latitude: float, longitude: float) -> None:
    """Уведомление администраторов о новой геолокации"""
    try:
        # Получаем список админов
        admins = UserService.get_admin_users()
        
        if not admins:
            logger.warning("Нет администраторов для уведомления о геолокации")
            return
        
        # Определяем тип участника
        participant = next(
            (p for p in game.participants if p.user_id == user.id),
            None
        )
        
        role_text = "Неизвестная роль"
        if participant and participant.role:
            role_text = "🚗 Водитель" if participant.role.value == 'driver' else "🔍 Искатель"
        
        # Формируем текст уведомления
        location_text = (
            f"📍 <b>Новая геолокация!</b>\n\n"
            f"👤 <b>От:</b> {user.name}\n"
            f"🎮 <b>Игра:</b> {game.district}\n"
            f"🎭 <b>Роль:</b> {role_text}\n"
            f"📅 <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"🌐 <b>Координаты:</b> {latitude:.6f}, {longitude:.6f}\n"
        )
        
        # Проверяем, находится ли пользователь в игровой зоне
        in_zone = LocationService.is_user_in_game_zone(user.id, game.id)
        location_text += f"🎯 <b>В игровой зоне:</b> {'✅' if in_zone else '❌'}\n"
        
        # Отправляем уведомления всем админам
        for admin in admins:
            try:
                # Отправляем сообщение с геолокацией
                await context.bot.send_location(
                    chat_id=admin.telegram_id,
                    latitude=latitude,
                    longitude=longitude
                )
                
                # Отправляем информацию о пользователе
                await context.bot.send_message(
                    chat_id=admin.telegram_id,
                    text=location_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin.telegram_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка уведомления админов о геолокации: {e}")

# Создаем обработчики
location_handlers = [
    MessageHandler(filters.LOCATION, handle_location),
    MessageHandler(filters.Regex("^📍 Отправить мою геолокацию$"), request_location_handler),
] 