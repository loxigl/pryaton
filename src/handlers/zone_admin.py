from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from loguru import logger
from typing import List

from src.services.user_service import UserService
from src.services.settings_service import SettingsService
from src.services.zone_management_service import ZoneManagementService
from src.keyboards.reply import get_contextual_main_keyboard

# Состояния для создания/редактирования зон
ZONE_SELECT_DISTRICT, ZONE_SELECT_ACTION, ZONE_CREATE_NAME, ZONE_CREATE_LAT, ZONE_CREATE_LON, ZONE_CREATE_RADIUS, ZONE_CREATE_DESCRIPTION, ZONE_CONFIRM = range(8)

async def zone_management_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда управления зонами районов"""
    user_id = update.effective_user.id
    
    if not UserService.is_admin(user_id):
        await update.message.reply_text(
            "❌ Доступ запрещен. Только для администраторов.",
            reply_markup=get_contextual_main_keyboard(user_id)
        )
        return ConversationHandler.END
    
    return await show_district_selection(update, context)

async def show_district_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать выбор района для управления зонами"""
    districts = SettingsService.get_districts()
    
    if not districts:
        text = "❌ В системе нет районов. Сначала создайте районы через админ-панель."
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END
    
    text = "🗺 <b>Управление зонами районов</b>\n\nВыберите район для управления зонами:"
    
    keyboard = []
    for district in districts:
        keyboard.append([InlineKeyboardButton(
            f"📍 {district}", 
            callback_data=f"zone_district_{district}"
        )])
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="zone_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="HTML", reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text, parse_mode="HTML", reply_markup=reply_markup
        )
    
    return ZONE_SELECT_DISTRICT

async def handle_district_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора района"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "zone_cancel":
        await query.edit_message_text("❌ Управление зонами отменено.")
        return ConversationHandler.END
    
    if not query.data.startswith("zone_district_"):
        return ZONE_SELECT_DISTRICT
    
    district_name = query.data.replace("zone_district_", "")
    context.user_data["selected_district"] = district_name
    
    return await show_zone_actions(update, context, district_name)

async def show_zone_actions(update: Update, context: ContextTypes.DEFAULT_TYPE, district_name: str) -> int:
    """Показать действия с зонами района"""
    zones_info = ZoneManagementService.get_district_zones_info(district_name)
    
    text = f"🗺 <b>Зоны района: {district_name}</b>\n\n"
    
    if zones_info:
        text += f"📋 <b>Существующие зоны ({len(zones_info)}):</b>\n\n"
        for zone in zones_info:
            default_mark = " 🌟" if zone["is_default"] else ""
            active_mark = "🟢" if zone["is_active"] else "🔴"
            text += (
                f"{active_mark} <b>{zone['zone_name']}</b>{default_mark}\n"
                f"   📍 {zone['center_lat']:.4f}, {zone['center_lon']:.4f}\n"
                f"   📏 Радиус: {zone['radius']}м ({zone['area_km2']} км²)\n\n"
            )
    else:
        text += "📭 В этом районе пока нет зон.\n\n"
    
    text += "Выберите действие:"
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать зону", callback_data="zone_create")],
    ]
    
    if zones_info:
        keyboard.extend([
            [InlineKeyboardButton("✏️ Редактировать зону", callback_data="zone_edit")],
            [InlineKeyboardButton("🗑 Удалить зону", callback_data="zone_delete")],
            [InlineKeyboardButton("🧪 Тестировать точку", callback_data="zone_test")],
        ])
    else:
        keyboard.append([InlineKeyboardButton("🏗 Создать зоны по умолчанию", callback_data="zone_create_default")])
    
    keyboard.extend([
        [InlineKeyboardButton("« Назад к районам", callback_data="zone_back_districts")],
        [InlineKeyboardButton("❌ Отмена", callback_data="zone_cancel")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query = update.callback_query
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)
    
    return ZONE_SELECT_ACTION

async def handle_zone_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка действий с зонами"""
    query = update.callback_query
    await query.answer()
    
    district_name = context.user_data.get("selected_district")
    
    if query.data == "zone_cancel":
        await query.edit_message_text("❌ Управление зонами отменено.")
        return ConversationHandler.END
    elif query.data == "zone_back_districts":
        return await show_district_selection(update, context)
    elif query.data == "zone_create":
        return await start_zone_creation(update, context)
    elif query.data == "zone_create_default":
        return await create_default_zones(update, context, district_name)
    elif query.data == "zone_edit":
        return await show_zones_for_edit(update, context, district_name)
    elif query.data == "zone_delete":
        return await show_zones_for_delete(update, context, district_name)
    elif query.data == "zone_test":
        return await start_zone_testing(update, context, district_name)
    
    return ZONE_SELECT_ACTION

async def start_zone_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать создание новой зоны"""
    query = update.callback_query
    district_name = context.user_data.get("selected_district")
    
    text = (
        f"➕ <b>Создание зоны для района: {district_name}</b>\n\n"
        f"Введите название зоны:\n"
        f"(например: 'Центр города', 'Парк Горького', 'Торговый центр')"
    )
    
    await query.edit_message_text(text, parse_mode="HTML")
    return ZONE_CREATE_NAME

async def process_zone_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка названия зоны"""
    zone_name = update.message.text.strip()
    
    if len(zone_name) < 2:
        await update.message.reply_text("❌ Название зоны должно содержать минимум 2 символа.")
        return ZONE_CREATE_NAME
    
    context.user_data["zone_name"] = zone_name
    
    await update.message.reply_text(
        f"✅ Название: <b>{zone_name}</b>\n\n"
        f"📍 Теперь введите широту центра зоны:\n"
        f"(например: 55.7558)",
        parse_mode="HTML"
    )
    
    return ZONE_CREATE_LAT

async def process_zone_lat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка широты зоны"""
    try:
        lat = float(update.message.text.strip())
        if not (-90 <= lat <= 90):
            raise ValueError("Широта должна быть от -90 до 90")
        
        context.user_data["zone_lat"] = lat
        
        await update.message.reply_text(
            f"✅ Широта: <b>{lat}</b>\n\n"
            f"📍 Теперь введите долготу центра зоны:\n"
            f"(например: 37.6176)",
            parse_mode="HTML"
        )
        
        return ZONE_CREATE_LON
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат широты. Введите число от -90 до 90\n"
            "(например: 55.7558)"
        )
        return ZONE_CREATE_LAT

async def process_zone_lon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка долготы зоны"""
    try:
        lon = float(update.message.text.strip())
        if not (-180 <= lon <= 180):
            raise ValueError("Долгота должна быть от -180 до 180")
        
        context.user_data["zone_lon"] = lon
        
        await update.message.reply_text(
            f"✅ Долгота: <b>{lon}</b>\n\n"
            f"📏 Теперь введите радиус зоны в метрах:\n"
            f"(например: 1000 для 1 км)",
            parse_mode="HTML"
        )
        
        return ZONE_CREATE_RADIUS
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат долготы. Введите число от -180 до 180\n"
            "(например: 37.6176)"
        )
        return ZONE_CREATE_LON

async def process_zone_radius(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка радиуса зоны"""
    try:
        radius = int(update.message.text.strip())
        if radius <= 0:
            raise ValueError("Радиус должен быть больше 0")
        if radius > 50000:  # 50 км максимум
            raise ValueError("Радиус не может быть больше 50000 метров")
        
        context.user_data["zone_radius"] = radius
        
        area_km2 = round((3.14159 * (radius / 1000) ** 2), 2)
        
        await update.message.reply_text(
            f"✅ Радиус: <b>{radius} метров</b> (площадь: {area_km2} км²)\n\n"
            f"📝 Введите описание зоны (необязательно):\n"
            f"Или отправьте '-' чтобы пропустить.",
            parse_mode="HTML"
        )
        
        return ZONE_CREATE_DESCRIPTION
        
    except ValueError as e:
        await update.message.reply_text(
            f"❌ Неверный формат радиуса. {str(e)}\n"
            "Введите целое число от 1 до 50000"
        )
        return ZONE_CREATE_RADIUS

async def process_zone_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка описания зоны"""
    description = update.message.text.strip()
    if description == "-":
        description = None
    
    context.user_data["zone_description"] = description
    
    # Показываем итоговую информацию
    zone_name = context.user_data["zone_name"]
    zone_lat = context.user_data["zone_lat"]
    zone_lon = context.user_data["zone_lon"]
    zone_radius = context.user_data["zone_radius"]
    district_name = context.user_data["selected_district"]
    
    area_km2 = round((3.14159 * (zone_radius / 1000) ** 2), 2)
    
    text = (
        f"📋 <b>Подтверждение создания зоны</b>\n\n"
        f"🏙 <b>Район:</b> {district_name}\n"
        f"📍 <b>Название:</b> {zone_name}\n"
        f"🌍 <b>Координаты:</b> {zone_lat}, {zone_lon}\n"
        f"📏 <b>Радиус:</b> {zone_radius}м ({area_km2} км²)\n"
    )
    
    if description:
        text += f"📝 <b>Описание:</b> {description}\n"
    
    text += "\nСоздать эту зону?"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Создать", callback_data="zone_confirm_create"),
            InlineKeyboardButton("❌ Отмена", callback_data="zone_cancel_create")
        ]
    ]
    
    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ZONE_CONFIRM

async def handle_zone_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка подтверждения создания зоны"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "zone_cancel_create":
        district_name = context.user_data["selected_district"]
        await query.edit_message_text("❌ Создание зоны отменено.")
        # Возвращаемся к действиям с зонами
        return await show_zone_actions(update, context, district_name)
    
    if query.data == "zone_confirm_create":
        # Создаём зону
        district_name = context.user_data["selected_district"]
        zone_name = context.user_data["zone_name"]
        zone_lat = context.user_data["zone_lat"]
        zone_lon = context.user_data["zone_lon"]
        zone_radius = context.user_data["zone_radius"]
        zone_description = context.user_data.get("zone_description")
        
        # Проверяем, есть ли уже зоны в районе (если нет, делаем эту зоной по умолчанию)
        existing_zones = ZoneManagementService.get_district_zones_info(district_name)
        is_default = len(existing_zones) == 0
        
        zone = ZoneManagementService.create_district_zone(
            district_name=district_name,
            zone_name=zone_name,
            center_lat=zone_lat,
            center_lon=zone_lon,
            radius=zone_radius,
            description=zone_description,
            is_default=is_default
        )
        
        if zone:
            default_text = " (установлена как зона по умолчанию)" if is_default else ""
            await query.edit_message_text(
                f"✅ <b>Зона создана!</b>\n\n"
                f"📍 Зона '{zone_name}' успешно создана для района {district_name}{default_text}",
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при создании зоны. Попробуйте еще раз."
            )
        
        # Очищаем данные
        context.user_data.clear()
        return ConversationHandler.END
    
    return ZONE_CONFIRM

async def create_default_zones(update: Update, context: ContextTypes.DEFAULT_TYPE, district_name: str) -> int:
    """Создание зон по умолчанию"""
    query = update.callback_query
    
    success = ZoneManagementService.create_default_zones_for_district(district_name)
    
    if success:
        text = (
            f"✅ <b>Зона по умолчанию создана!</b>\n\n"
            f"Для района '{district_name}' создана базовая зона.\n"
            f"⚠️ Обязательно настройте правильные координаты!"
        )
    else:
        text = "❌ Не удалось создать зоны по умолчанию."
    
    await query.edit_message_text(text, parse_mode="HTML")
    return ConversationHandler.END

async def start_zone_testing(update: Update, context: ContextTypes.DEFAULT_TYPE, district_name: str) -> int:
    """Начать тестирование точки в зонах"""
    query = update.callback_query
    
    text = (
        f"🧪 <b>Тестирование зон района: {district_name}</b>\n\n"
        f"Отправьте геолокацию или введите координаты в формате:\n"
        f"широта,долгота\n\n"
        f"Например: 55.7558,37.6176"
    )
    
    await query.edit_message_text(text, parse_mode="HTML")
    # Этот функционал можно доработать позже
    return ConversationHandler.END

# Вспомогательные функции (заглушки для полного функционала)
async def show_zones_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, district_name: str) -> int:
    """Показать зоны для редактирования"""
    query = update.callback_query
    await query.edit_message_text(
        "✏️ Функция редактирования зон будет добавлена в следующих обновлениях."
    )
    return ConversationHandler.END

async def show_zones_for_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, district_name: str) -> int:
    """Показать зоны для удаления"""
    query = update.callback_query
    await query.edit_message_text(
        "🗑 Функция удаления зон будет добавлена в следующих обновлениях."
    )
    return ConversationHandler.END

async def cancel_zone_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена управления зонами"""
    await update.message.reply_text("❌ Управление зонами отменено.")
    return ConversationHandler.END

# Conversation handler для управления зонами
zone_management_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^🗺 Управление зонами$"), zone_management_command)
    ],
    states={
        ZONE_SELECT_DISTRICT: [
            CallbackQueryHandler(handle_district_selection, pattern="^zone_")
        ],
        ZONE_SELECT_ACTION: [
            CallbackQueryHandler(handle_zone_action, pattern="^zone_")
        ],
        ZONE_CREATE_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_name)
        ],
        ZONE_CREATE_LAT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_lat)
        ],
        ZONE_CREATE_LON: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_lon)
        ],
        ZONE_CREATE_RADIUS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_radius)
        ],
        ZONE_CREATE_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_zone_description)
        ],
        ZONE_CONFIRM: [
            CallbackQueryHandler(handle_zone_confirmation, pattern="^zone_")
        ]
    },
    fallbacks=[
        MessageHandler(filters.Regex("^❌ Отмена$"), cancel_zone_management)
    ]
) 