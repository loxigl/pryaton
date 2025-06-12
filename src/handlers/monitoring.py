from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from loguru import logger
from datetime import datetime, timedelta
import psutil

from src.services.enhanced_scheduler_service import DEFAULT_TIMEZONE
from src.services.user_service import UserService
from src.services.monitoring_service import MonitoringService
from src.keyboards.reply import get_contextual_main_keyboard

# Состояния для диалогов мониторинга
MONITORING_MENU, VIEW_GAME_DETAILS, VIEW_PLAYER_STATS = range(3)

def format_msk_time(dt: datetime) -> str:
    """Форматирует время в МСК"""
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%H:%M')

def format_msk_datetime(dt: datetime) -> str:
    """Форматирует дату и время в МСК"""
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%d.%m.%Y %H:%M')

async def monitoring_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда мониторинга для админов"""
    user_id = update.effective_user.id
    
    logger.info(f"Запрос мониторинга от пользователя {user_id}")
    
    if not UserService.is_admin(user_id):
        logger.warning(f"Отказ в доступе к мониторингу для пользователя {user_id}")
        await update.message.reply_text(
            "❌ Доступ запрещен. Только для администраторов.",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        return ConversationHandler.END
    
    logger.info(f"Переход в состояние мониторинга для пользователя {user_id}")
    return await show_monitoring_menu(update, context)

async def show_monitoring_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать главное меню мониторинга"""
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
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    
    return MONITORING_MENU

async def show_active_games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать активные игры"""
    query = update.callback_query
    await query.answer()
    
    stats = MonitoringService.get_active_games_stats()
    active_games = stats.get('active_games', [])
    
    if not active_games:
        text = "🎮 <b>Активные игры</b>\n\nНет активных игр."
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="mon_back")]]
    else:
        text = f"🎮 <b>Активные игры ({len(active_games)})</b>\n\n"
        
        keyboard = []
        for game in active_games:
            game_info = f"#{game['id']} {game['district']} ({game['participants']}/{game['max_participants']})"
            text += f"• <b>Игра #{game['id']}</b>\n"
            text += f"  📍 {game['district']}\n"
            text += f"  ⏰ {format_msk_datetime(game['scheduled_at'])}\n"
            text += f"  🚦 {game['status']}\n"
            text += f"  👥 {game['participants']}/{game['max_participants']}\n\n"
            
            keyboard.append([InlineKeyboardButton(
                f"📋 Детали #{game['id']}", 
                callback_data=f"mon_game_details_{game['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="mon_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    
    return MONITORING_MENU

async def show_game_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать детали игры"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID игры из callback_data
    game_id = int(query.data.split('_')[-1])
    
    game_info = MonitoringService.get_game_detailed_info(game_id)
    if not game_info:
        text = "❌ Игра не найдена."
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="mon_active_games")]]
    else:
        game = game_info['game']
        participants = game_info['participants']
        summary = game_info['summary']
        
        text = f"📋 <b>ДЕТАЛИ ИГРЫ #{game['id']}</b>\n\n"
        text += f"📍 <b>Район:</b> {game['district']}\n"
        text += f"🚦 <b>Статус:</b> {game['status']}\n"
        text += f"⏰ <b>Запланировано:</b> {format_msk_datetime(game['scheduled_at'])}\n"
        
        if game['started_at']:
            text += f"🚀 <b>Начато:</b> {format_msk_datetime(game['started_at'])}\n"
        
        if game['ended_at']:
            text += f"🏁 <b>Завершено:</b> {format_msk_datetime(game['ended_at'])}\n"
        
        text += f"\n👥 <b>Участники:</b> {summary['total_participants']}/{game['max_participants']}\n"
        text += f"🚗 <b>Водители:</b> {summary['drivers_count']} (найдено: {summary['found_drivers']})\n"
        text += f"🔍 <b>Искатели:</b> {summary['seekers_count']}\n"
        text += f"📍 <b>С геолокацией:</b> {summary['participants_with_location']}\n"
        text += f"📸 <b>Всего фото:</b> {summary['total_photos']}\n\n"
        
        text += f"📋 <b>Список участников:</b>\n"
        for participant in participants:
            status_emoji = "✅" if participant['is_found'] else "❌"
            location_emoji = "📍" if participant['has_location'] else "📍❌"
            
            text += f"• {participant['name']} ({participant['role']}) {status_emoji}{location_emoji}\n"
        
        keyboard = [
            [InlineKeyboardButton("📊 Генерировать отчет", callback_data=f"mon_generate_report_{game_id}")],
            [InlineKeyboardButton("🗺 Показать карту", callback_data=f"mon_show_map_{game_id}")],
            [InlineKeyboardButton("↩️ К активным играм", callback_data="mon_active_games")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="mon_back")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    
    return MONITORING_MENU

async def generate_game_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Генерировать отчет по игре"""
    query = update.callback_query
    await query.answer()
    
    game_id = int(query.data.split('_')[-1])
    
    report = MonitoringService.generate_game_report(game_id)
    if not report:
        text = "❌ Ошибка генерации отчета."
    else:
        text = report
    
    keyboard = [
        [InlineKeyboardButton("↩️ К деталям игры", callback_data=f"mon_game_details_{game_id}")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="mon_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    
    return MONITORING_MENU

async def show_player_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать статистику игроков"""
    query = update.callback_query
    await query.answer()
    
    stats = MonitoringService.get_player_statistics()
    top_players = stats.get('top_players', [])
    
    text = f"📊 <b>СТАТИСТИКА ИГРОКОВ</b>\n\n"
    
    if not top_players:
        text += "Нет данных о игроках."
    else:
        text += f"🏆 <b>Топ-{len(top_players)} активных игроков:</b>\n\n"
        
        for i, player in enumerate(top_players, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {player['name']} - {player['games_count']} игр\n"
    
    keyboard = [
        [InlineKeyboardButton("🗺 Статистика районов", callback_data="mon_district_stats")],
        [InlineKeyboardButton("↩️ Назад", callback_data="mon_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    
    return MONITORING_MENU

async def show_district_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать статистику по районам"""
    query = update.callback_query
    await query.answer()
    
    stats = MonitoringService.get_district_statistics()
    
    text = f"🗺 <b>СТАТИСТИКА ПО РАЙОНАМ</b>\n\n"
    
    games_by_district = stats.get('games_by_district', [])
    players_by_district = stats.get('players_by_district', [])
    
    if games_by_district:
        text += f"🎮 <b>Игры по районам:</b>\n"
        for district in games_by_district[:10]:  # Топ-10
            text += f"• {district['district']}: {district['games_count']} игр\n"
        text += "\n"
    
    if players_by_district:
        text += f"👥 <b>Игроки по районам:</b>\n"
        for district in players_by_district[:10]:  # Топ-10
            text += f"• {district['district']}: {district['players_count']} игроков\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика игроков", callback_data="mon_player_stats")],
        [InlineKeyboardButton("↩️ Назад", callback_data="mon_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    
    return MONITORING_MENU

async def show_recent_activities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать последние активности"""
    query = update.callback_query
    await query.answer()
    
    activities = MonitoringService.get_recent_activities(15)
    
    text = f"📝 <b>ПОСЛЕДНИЕ АКТИВНОСТИ</b>\n\n"
    
    if not activities:
        text += "Нет активностей для отображения."
    else:
        for activity in activities:
            time_str = activity['timestamp'].strftime('%d.%m %H:%M')
            
            if activity['type'] == 'game_created':
                emoji = "🎮"
            elif activity['type'] == 'game_joined':
                emoji = "👤"
            else:
                emoji = "📝"
            
            text += f"{emoji} <code>{time_str}</code> {activity['description']}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="mon_recent_activities")],
        [InlineKeyboardButton("↩️ Назад", callback_data="mon_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    
    return MONITORING_MENU

async def handle_monitoring_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик callback'ов мониторинга"""
    query = update.callback_query
    data = query.data
    
    logger.info(f"Обработка callback мониторинга: {data} от пользователя {query.from_user.id}")
    
    if data == "mon_back" or data == "mon_refresh":
        logger.info(f"Возврат в главное меню мониторинга")
        return await show_monitoring_menu(update, context)
    elif data == "mon_active_games":
        logger.info(f"Показ активных игр")
        return await show_active_games(update, context)
    elif data.startswith("mon_game_details_"):
        logger.info(f"Показ деталей игры")
        return await show_game_details(update, context)
    elif data.startswith("mon_generate_report_"):
        logger.info(f"Генерация отчета")
        return await generate_game_report(update, context)
    elif data.startswith("mon_show_map_"):
        logger.info(f"Показ карты")
        # Интеграция с обработчиком карт из location.py
        from src.handlers.location import show_game_map
        await show_game_map(update, context)
        return MONITORING_MENU
    elif data == "mon_player_stats":
        logger.info(f"Статистика игроков")
        return await show_player_stats(update, context)
    elif data == "mon_district_stats":
        logger.info(f"Статистика районов")
        return await show_district_stats(update, context)
    elif data == "mon_recent_activities":
        logger.info(f"Последние активности")
        return await show_recent_activities(update, context)
    elif data == "mon_exit":
        logger.info(f"Выход из мониторинга")
        # Возвращаемся в главное меню
        is_admin = UserService.is_admin(query.from_user.id)
        await query.edit_message_text(
            "📊 Мониторинг завершен. Возвращение в главное меню."
        )
        await query.message.reply_text(
            "🏠 <b>Главное меню</b>\n\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=get_contextual_main_keyboard(query.from_user.id)
        )
        return ConversationHandler.END
    else:
        logger.warning(f"Неизвестный callback мониторинга: {data}")
    
    return MONITORING_MENU

# Создаем обработчики
monitoring_handlers = [
    MessageHandler(filters.Regex("^📊 Мониторинг$"), monitoring_command),
]

async def handle_monitoring_callback_direct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback'ов мониторинга без ConversationHandler"""
    query = update.callback_query
    data = query.data
    
    logger.info(f"Прямая обработка callback мониторинга: {data} от пользователя {query.from_user.id}")
    
    try:
        if data == "mon_back" or data == "mon_refresh":
            logger.info(f"Возврат в главное меню мониторинга")
            await show_monitoring_menu_direct(update, context)
        elif data == "mon_active_games":
            logger.info(f"Показ активных игр")
            await show_active_games_direct(update, context)
        elif data.startswith("mon_game_details_"):
            logger.info(f"Показ деталей игры")
            await show_game_details_direct(update, context)
        elif data.startswith("mon_generate_report_"):
            logger.info(f"Генерация отчета")
            await generate_game_report_direct(update, context)
        elif data.startswith("mon_show_map_"):
            logger.info(f"Показ карты")
            # Интеграция с обработчиком карт из location.py
            from src.handlers.location import show_game_map
            await show_game_map(update, context)
        elif data == "mon_player_stats":
            logger.info(f"Статистика игроков")
            await show_player_stats_direct(update, context)
        elif data == "mon_district_stats":
            logger.info(f"Статистика районов")
            await show_district_stats_direct(update, context)
        elif data == "mon_recent_activities":
            logger.info(f"Последние активности")
            await show_recent_activities_direct(update, context)
        elif data == "mon_exit":
            logger.info(f"Выход из мониторинга")
            # Возвращаемся в главное меню
            is_admin = UserService.is_admin(query.from_user.id)
            await query.edit_message_text(
                "📊 Мониторинг завершен. Возвращение в главное меню."
            )
            await query.message.reply_text(
                "🏠 <b>Главное меню</b>\n\nВыберите действие:",
                parse_mode="HTML",
                reply_markup=get_contextual_main_keyboard(query.from_user.id)
            )
        else:
            logger.warning(f"Неизвестный callback мониторинга: {data}")
            await query.answer("Неизвестная команда мониторинга")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке callback мониторинга {data}: {e}")
        await query.answer("Произошла ошибка при обработке команды мониторинга")

# Прямые функции для работы без ConversationHandler
async def show_monitoring_menu_direct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать главное меню мониторинга (прямой вызов)"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Вызываем функцию, но игнорируем возврат состояния
    try:
        await show_monitoring_menu(update, context)
    except Exception as e:
        logger.error(f"Ошибка показа меню мониторинга: {e}")

async def show_active_games_direct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать активные игры (прямой вызов)"""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        await show_active_games(update, context)
    except Exception as e:
        logger.error(f"Ошибка показа активных игр: {e}")

async def show_game_details_direct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать детали игры (прямой вызов)"""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        await show_game_details(update, context)
    except Exception as e:
        logger.error(f"Ошибка показа деталей игры: {e}")

async def generate_game_report_direct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Генерировать отчет по игре (прямой вызов)"""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        await generate_game_report(update, context)
    except Exception as e:
        logger.error(f"Ошибка генерации отчета: {e}")

async def show_player_stats_direct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статистику игроков (прямой вызов)"""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        await show_player_stats(update, context)
    except Exception as e:
        logger.error(f"Ошибка показа статистики игроков: {e}")

async def show_district_stats_direct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статистику по районам (прямой вызов)"""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        await show_district_stats(update, context)
    except Exception as e:
        logger.error(f"Ошибка показа статистики районов: {e}")

async def show_recent_activities_direct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать последние активности (прямой вызов)"""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        await show_recent_activities(update, context)
    except Exception as e:
        logger.error(f"Ошибка показа активностей: {e}")

# Conversation handler для мониторинга (оставляем для совместимости)
monitoring_conversation = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📊 Мониторинг$"), monitoring_command)],
    states={
        MONITORING_MENU: [CallbackQueryHandler(handle_monitoring_callback, pattern="^mon_")],
        VIEW_GAME_DETAILS: [CallbackQueryHandler(handle_monitoring_callback, pattern="^mon_")],
        VIEW_PLAYER_STATS: [CallbackQueryHandler(handle_monitoring_callback, pattern="^mon_")]
    },
    fallbacks=[]
) 