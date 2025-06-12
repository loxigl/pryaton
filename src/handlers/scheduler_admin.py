import os
import pytz
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from datetime import datetime, timezone, timedelta
import re
from loguru import logger

from src.models.game import GameRole, GameStatus
from src.services.user_service import UserService
from src.services.game_service import GameService
from src.services.enhanced_scheduler_service import get_enhanced_scheduler
from src.services.event_persistence_service import EventPersistenceService
from src.keyboards.reply import get_contextual_main_keyboard, get_district_keyboard
from src.handlers.admin import get_admin_keyboard, get_admin_or_main_keyboard,ConversationHandler
from src.models.base import get_db

DEFAULT_TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "Europe/Moscow"))

def format_msk_time(dt: datetime) -> str:
    """Форматирует время в МСК"""
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%H:%M')

def format_msk_datetime(dt: datetime) -> str:
    """Форматирует дату и время в МСК"""
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%d.%m.%Y %H:%M')

async def scheduler_monitor_command(update: Update, context: CallbackContext) -> None:
    """Команда /scheduler_monitor - показывает состояние планировщика"""
    user_id = update.effective_user.id
    # Проверяем, является ли пользователь администратором
    if not UserService.is_admin(user_id):
        await update.message.reply_text("У вас нет прав доступа к этой команде.")
        return
    
    scheduler = get_enhanced_scheduler()
    if not scheduler:
        await update.message.reply_text("❌ Планировщик не инициализирован")
        return
    
    # Получаем информацию о событиях
    events_info = scheduler.get_scheduled_events_info()
    events_by_game = events_info["events_by_game"]
    stats = events_info["statistics"]
    scheduler_jobs = events_info["scheduler_jobs"]
    
    # Формируем текст отчета
    report_text = (
        f"⏰ <b>Мониторинг планировщика</b>\n\n"
        f"📊 <b>Статистика событий:</b>\n"
        f"• Всего событий: {stats.get('total', 0)}\n"
        f"• Выполнено: {stats.get('executed', 0)}\n"
        f"• Запланировано: {stats.get('pending', 0)}\n"
        f"• Просрочено: {stats.get('overdue', 0)}\n"
        f"• Задач в планировщике: {scheduler_jobs}\n\n"
    )
    
    if events_by_game:
        report_text += "🎮 <b>События по играм:</b>\n\n"
        
        for game_id, events in list(events_by_game.items())[:5]:  # Показываем первые 5 игр
            game = GameService.get_game_by_id(game_id)
            game_name = f"Игра #{game_id}"
            if game:
                game_name = f"{game.district} ({format_msk_datetime(game.scheduled_at)})"
            
            report_text += f"🎯 <b>{game_name}</b>\n"
            
            for event in events[:3]:  # Показываем первые 3 события
                emoji = "✅" if event.is_executed else "⏳"
                if event.is_overdue:
                    emoji = "⚠️"
                
                event_name = event.event_type.replace("_", " ").title()
                time_str = format_msk_datetime(event.scheduled_at)
                
                report_text += f"  {emoji} {event_name} → {time_str}\n"
            
            if len(events) > 3:
                report_text += f"  ... и еще {len(events) - 3} событий\n"
            
            report_text += "\n"
    else:
        report_text += "📭 Нет запланированных событий\n"
    
    # Создаем клавиатуру с действиями
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="scheduler_refresh"),
            InlineKeyboardButton("📋 Все события", callback_data="scheduler_all_events")
        ],
        [
            InlineKeyboardButton("🧹 Очистить старые", callback_data="scheduler_cleanup"),
            InlineKeyboardButton("🧪 Тест события", callback_data="scheduler_test")
        ]
    ])
    
    await update.message.reply_text(
        report_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def scheduler_refresh_button(update: Update, context: CallbackContext) -> None:
    """Обновление информации о планировщике"""
    query = update.callback_query
    await query.answer("Обновляем...")
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    scheduler = get_enhanced_scheduler()
    if not scheduler:
        await query.edit_message_text("❌ Планировщик не инициализирован")
        return
    
    # Получаем обновленную информацию
    events_info = scheduler.get_scheduled_events_info()
    events_by_game = events_info["events_by_game"]
    stats = events_info["statistics"]
    scheduler_jobs = events_info["scheduler_jobs"]
    
    # Формируем обновленный текст
    report_text = (
        f"⏰ <b>Мониторинг планировщика</b> (обновлено {datetime.now().strftime('%H:%M:%S')})\n\n"
        f"📊 <b>Статистика событий:</b>\n"
        f"• Всего событий: {stats.get('total', 0)}\n"
        f"• Выполнено: {stats.get('executed', 0)}\n"
        f"• Запланировано: {stats.get('pending', 0)}\n"
        f"• Просрочено: {stats.get('overdue', 0)}\n"
        f"• Задач в планировщике: {scheduler_jobs}\n\n"
    )
    
    if events_by_game:
        report_text += "🎮 <b>События по играм:</b>\n\n"
        
        for game_id, events in list(events_by_game.items())[:5]:
            game = GameService.get_game_by_id(game_id)
            game_name = f"Игра #{game_id}"
            if game:
                game_name = f"{game.district} ({game.scheduled_at.strftime('%d.%m %H:%M')})"
            
            report_text += f"🎯 <b>{game_name}</b>\n"
            
            for event in events[:3]:
                emoji = "✅" if event.is_executed else "⏳"
                if event.is_overdue:
                    emoji = "⚠️"
                
                event_name = event.event_type.replace("_", " ").title()
                time_str = event.scheduled_at.strftime('%d.%m %H:%M')
                
                report_text += f"  {emoji} {event_name} → {time_str}\n"
            
            if len(events) > 3:
                report_text += f"  ... и еще {len(events) - 3} событий\n"
            
            report_text += "\n"
    else:
        report_text += "📭 Нет запланированных событий\n"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="scheduler_refresh"),
            InlineKeyboardButton("📋 Все события", callback_data="scheduler_all_events")
        ],
        [
            InlineKeyboardButton("🧹 Очистить старые", callback_data="scheduler_cleanup"),
            InlineKeyboardButton("🧪 Тест события", callback_data="scheduler_test")
        ]
    ])
    
    await query.edit_message_text(
        report_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def scheduler_all_events_button(update: Update, context: CallbackContext) -> None:
    """Показать все запланированные события"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    pending_events = EventPersistenceService.get_pending_events()
    
    if not pending_events:
        await query.edit_message_text("📭 Нет запланированных событий")
        return
    
    # Группируем события по играм
    events_by_game = {}
    for event in pending_events:
        if event.game_id not in events_by_game:
            events_by_game[event.game_id] = []
        events_by_game[event.game_id].append(event)
    
    report_text = f"📋 <b>Все запланированные события</b> ({len(pending_events)})\n\n"
    
    for game_id, events in events_by_game.items():
        game = GameService.get_game_by_id(game_id)
        game_name = f"Игра #{game_id}"
        if game:
            game_name = f"{game.district} ({game.scheduled_at.strftime('%d.%m %H:%M')})"
        
        report_text += f"🎮 <b>{game_name}</b>\n"
        
        for event in sorted(events, key=lambda x: x.scheduled_at):
            emoji = "⏳"
            if event.is_overdue:
                emoji = "⚠️"
            
            event_name = event.event_type.replace("_", " ").title()
            time_str = event.scheduled_at.strftime('%d.%m %H:%M')
            
            report_text += f"  {emoji} {event_name} → {time_str}\n"
        
        report_text += "\n"
        
        # Ограничиваем длину сообщения
        if len(report_text) > 3500:
            report_text += "... (показаны не все события)\n"
            break
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="scheduler_refresh")]
    ])
    
    await query.edit_message_text(
        report_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def scheduler_cleanup_button(update: Update, context: CallbackContext) -> None:
    """Очистка старых выполненных событий"""
    query = update.callback_query
    await query.answer("Очищаем старые события...")
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Очищаем события старше 7 дней
    deleted_count = EventPersistenceService.cleanup_old_events(days_old=7)
    
    await query.edit_message_text(
        f"🧹 <b>Очистка завершена</b>\n\n"
        f"Удалено старых событий: {deleted_count}\n\n"
        f"Нажмите 'Обновить' для просмотра актуального состояния.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data="scheduler_refresh")]
        ]),
        parse_mode="HTML"
    )


async def scheduler_test_button(update: Update, context: CallbackContext) -> None:
    """Тестирование функций планировщика"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Создаем клавиатуру с тестовыми функциями
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Восстановить события", callback_data="scheduler_test_restore"),
            InlineKeyboardButton("📊 Статистика", callback_data="scheduler_test_stats")
        ],
        [
            InlineKeyboardButton("⚠️ Проверить просроченные", callback_data="scheduler_test_overdue"),
        ],
        [
            InlineKeyboardButton("« Назад", callback_data="scheduler_refresh")
        ]
    ])
    
    current_time = datetime.now().strftime('%H:%M:%S')
    await query.edit_message_text(
        f"🧪 <b>Тестовые функции планировщика</b> ({current_time})\n\n"
        f"Выберите действие для тестирования:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def scheduler_test_restore_button(update: Update, context: CallbackContext) -> None:
    """Тест восстановления событий"""
    query = update.callback_query
    await query.answer("Восстанавливаем события...")
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    scheduler = get_enhanced_scheduler()
    if not scheduler:
        await query.edit_message_text("❌ Планировщик не инициализирован")
        return
    
    try:
        # Принудительно восстанавливаем события
        scheduler._restore_events_from_db()
        
        events_info = scheduler.get_scheduled_events_info()
        scheduler_jobs = events_info["scheduler_jobs"]
        
        await query.edit_message_text(
            f"✅ <b>Восстановление завершено</b>\n\n"
            f"Задач в планировщике: {scheduler_jobs}\n\n"
            f"События восстановлены из БД.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к тестам", callback_data="scheduler_test")]
            ]),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка восстановления событий: {e}")
        await query.edit_message_text(
            f"❌ <b>Ошибка восстановления</b>\n\n"
            f"Произошла ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к тестам", callback_data="scheduler_test")]
            ]),
            parse_mode="HTML"
        )


async def scheduler_test_stats_button(update: Update, context: CallbackContext) -> None:
    """Детальная статистика событий"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    stats = EventPersistenceService.get_events_statistics()
    
    report_text = (
        f"📊 <b>Детальная статистика событий</b>\n\n"
        f"📈 <b>Общие показатели:</b>\n"
        f"• Всего событий в БД: {stats.get('total', 0)}\n"
        f"• Выполненных: {stats.get('executed', 0)}\n"
        f"• Ожидающих выполнения: {stats.get('pending', 0)}\n"
        f"• Просроченных: {stats.get('overdue', 0)}\n\n"
    )
    
    if stats.get('total', 0) > 0:
        executed_percent = round((stats.get('executed', 0) / stats.get('total', 1)) * 100, 1)
        overdue_percent = round((stats.get('overdue', 0) / stats.get('total', 1)) * 100, 1)
        
        report_text += (
            f"📊 <b>Процентные показатели:</b>\n"
            f"• Выполнено: {executed_percent}%\n"
            f"• Просрочено: {overdue_percent}%\n"
        )
    
    await query.edit_message_text(
        report_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« Назад к тестам", callback_data="scheduler_test")]
        ]),
        parse_mode="HTML"
    )


async def scheduler_test_overdue_button(update: Update, context: CallbackContext) -> None:
    """Проверка просроченных событий"""
    query = update.callback_query
    await query.answer("Проверяем просроченные события...")
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Получаем все невыполненные события
    pending_events = EventPersistenceService.get_pending_events()
    overdue_events = [e for e in pending_events if e.is_overdue]
    
    if not overdue_events:
        await query.edit_message_text(
            "✅ <b>Просроченных событий нет</b>\n\n"
            "Все события выполняются по расписанию.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к тестам", callback_data="scheduler_test")]
            ]),
            parse_mode="HTML"
        )
        return
    
    report_text = f"⚠️ <b>Найдено просроченных событий: {len(overdue_events)}</b>\n\n"
    
    for event in overdue_events[:10]:  # Показываем первые 10
        game = GameService.get_game_by_id(event.game_id)
        game_name = f"Игра #{event.game_id}"
        if game:
            game_name = f"{game.district}"
        
        event_name = event.event_type.replace("_", " ").title()
        time_str = event.scheduled_at.strftime('%d.%m %H:%M')
        overdue_hours = int((datetime.now() - event.scheduled_at).total_seconds() / 3600)
        
        report_text += f"• {game_name}: {event_name}\n"
        report_text += f"  Должно было: {time_str} (просрочено на {overdue_hours}ч)\n\n"
    
    if len(overdue_events) > 10:
        report_text += f"... и еще {len(overdue_events) - 10} событий\n\n"
    
    report_text += "🔧 Рекомендуется проверить состояние планировщика."
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Отметить выполненными", callback_data="scheduler_mark_overdue")],
        [InlineKeyboardButton("« Назад к тестам", callback_data="scheduler_test")]
    ])
    
    await query.edit_message_text(
        report_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def scheduler_mark_overdue_button(update: Update, context: CallbackContext) -> None:
    """Отметить просроченные события как выполненные"""
    query = update.callback_query
    await query.answer("Отмечаем просроченные события...")
    
    user_id = query.from_user.id
    if not UserService.is_admin(user_id):
        await query.edit_message_text("У вас нет прав доступа.")
        return
    
    # Получаем просроченные события
    pending_events = EventPersistenceService.get_pending_events()
    overdue_events = [e for e in pending_events if e.is_overdue]
    
    if not overdue_events:
        await query.edit_message_text(
            "✅ Просроченных событий не найдено",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к тестам", callback_data="scheduler_test")]
            ])
        )
        return
    
    # Отмечаем как выполненные
    marked_count = 0
    for event in overdue_events:
        if EventPersistenceService.mark_event_executed(event.id):
            marked_count += 1
    
    await query.edit_message_text(
        f"✅ <b>Просроченные события обработаны</b>\n\n"
        f"Отмечено как выполненных: {marked_count} из {len(overdue_events)}\n\n"
        f"События больше не будут отображаться как просроченные.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« Назад к тестам", callback_data="scheduler_test")]
        ]),
        parse_mode="HTML"
    )


# Регистрация хендлеров
def register_scheduler_admin_handlers(application):
    """Регистрация хендлеров админки планировщика"""
    
    # Команда мониторинга
    application.add_handler(CommandHandler("scheduler_monitor", scheduler_monitor_command))
    
    # Callback-хендлеры
    application.add_handler(CallbackQueryHandler(scheduler_refresh_button, pattern="scheduler_refresh"))
    application.add_handler(CallbackQueryHandler(scheduler_all_events_button, pattern="scheduler_all_events"))
    application.add_handler(CallbackQueryHandler(scheduler_cleanup_button, pattern="scheduler_cleanup"))
    application.add_handler(CallbackQueryHandler(scheduler_test_button, pattern="scheduler_test"))
    application.add_handler(CallbackQueryHandler(scheduler_test_restore_button, pattern="scheduler_test_restore"))
    application.add_handler(CallbackQueryHandler(scheduler_test_stats_button, pattern="scheduler_test_stats"))
    application.add_handler(CallbackQueryHandler(scheduler_test_overdue_button, pattern="scheduler_test_overdue"))
    application.add_handler(CallbackQueryHandler(scheduler_mark_overdue_button, pattern="scheduler_mark_overdue"))