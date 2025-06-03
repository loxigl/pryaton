from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, Contact
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger
import os

from src.models.base import get_db
from src.models.user import User, UserRole
from src.services.user_service import UserService
from src.services.settings_service import SettingsService
from src.keyboards import (
    get_phone_keyboard, 
    get_district_keyboard, 
    get_role_keyboard, 
    get_confirmation_keyboard,
    get_main_keyboard,
    get_contextual_main_keyboard,
    remove_keyboard
)

# Состояния для FSM регистрации
ENTER_NAME, ENTER_PHONE, ENTER_DISTRICT, ENTER_ROLE, CONFIRM_RULES = range(5)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик старта бота, начинает диалог регистрации или показывает главное меню"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.username}) запустил бота")
    
    # Проверка наличия пользователя в БД
    db_generator = get_db()
    db = next(db_generator)
    
    db_user = db.query(User).filter(User.telegram_id == user.id).first()
    
    if db_user:
        # Пользователь уже зарегистрирован
        logger.info(f"Пользователь {user.id} уже зарегистрирован")
        
        welcome_text = (
            f"🎉 <b>С возвращением, {db_user.name}!</b>\n\n"
            f"🏠 Добро пожаловать в главное меню бота PRYATON.\n"
            f"Выберите нужное действие из меню ниже:"
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_contextual_main_keyboard(user.id),
            parse_mode="HTML"
        )
        return ConversationHandler.END
    
    # Новый пользователь, начинаем регистрацию
    welcome_text = (
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        f"🎮 Добро пожаловать в бота проекта <b>PRYATON</b>.\n\n"
        f"Для начала работы нам нужно зарегистрировать вас в системе.\n\n"
        f"📝 <b>Как вас зовут?</b>\n"
        f"(Введите имя или ник, который будет виден другим участникам)"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML"
    )
    
    # Возвращаем следующее состояние для ConversationHandler
    return ENTER_NAME

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода имени пользователя"""
    user = update.effective_user
    name = update.message.text
    
    # Проверяем валидность имени
    if len(name.strip()) < 2:
        await update.message.reply_text(
            "❌ Имя должно содержать минимум 2 символа. Попробуйте еще раз:"
        )
        return ENTER_NAME
    
    if len(name) > 50:
        await update.message.reply_text(
            "❌ Имя слишком длинное (максимум 50 символов). Попробуйте еще раз:"
        )
        return ENTER_NAME
    
    # Сохраняем имя во временное хранилище
    context.user_data["name"] = name.strip()
    logger.info(f"Пользователь {user.id} ввел имя: {name}")
    
    # Запрашиваем номер телефона
    phone_text = (
        f"✅ <b>Отлично, {name}!</b>\n\n"
        f"📱 <b>Поделитесь номером телефона</b>\n"
        f"Это поможет организаторам связаться с вами при необходимости.\n\n"
        f"Вы можете поделиться контактом или пропустить этот шаг."
    )
    
    await update.message.reply_text(
        phone_text,
        reply_markup=get_phone_keyboard(),
        parse_mode="HTML"
    )
    
    return ENTER_PHONE

async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода номера телефона"""
    user = update.effective_user
    
    if update.message.contact:
        # Пользователь поделился контактом
        phone = update.message.contact.phone_number
        logger.info(f"Пользователь {user.id} поделился номером телефона: {phone}")
        success_text = "✅ Контакт получен!"
    elif update.message.text == "⏭ Пропустить":
        # Пользователь пропустил ввод телефона
        phone = None
        logger.info(f"Пользователь {user.id} пропустил ввод номера телефона")
        success_text = "⏭ Телефон пропущен"
    else:
        # Пользователь ввел номер вручную
        phone = update.message.text
        logger.info(f"Пользователь {user.id} ввел номер телефона: {phone}")
        success_text = "✅ Номер телефона сохранен!"
    
    # Сохраняем телефон во временное хранилище
    context.user_data["phone"] = phone
    
    # Запрашиваем район
    district_text = (
        f"{success_text}\n\n"
        f"📍 <b>Выберите ваш район</b>\n"
        f"Это поможет подбирать игры в удобном для вас месте:"
    )
    
    await update.message.reply_text(
        district_text,
        reply_markup=get_district_keyboard(),
        parse_mode="HTML"
    )
    
    return ENTER_DISTRICT

async def process_district(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора района"""
    user = update.effective_user
    district = update.message.text
    
    # Проверяем, что выбран валидный район
    available_districts = SettingsService.get_districts()
    if district not in available_districts:
        await update.message.reply_text(
            "❌ Пожалуйста, выберите район из предложенного списка:",
            reply_markup=get_district_keyboard()
        )
        return ENTER_DISTRICT
    
    # Сохраняем район во временное хранилище
    context.user_data["district"] = district
    logger.info(f"Пользователь {user.id} выбрал район: {district}")
    
    # Запрашиваем роль по умолчанию
    role_text = (
        f"✅ <b>Район: {district}</b>\n\n"
        f"🎭 <b>Выберите роль по умолчанию</b>\n"
        f"Это ваша предпочитаемая роль в играх:\n\n"
        f"🔍 <b>Игрок</b> - ищет спрятавшегося водителя\n"
        f"🚗 <b>Водитель</b> - прячется от игроков\n"
        f"👁 <b>Наблюдатель</b> - наблюдает за игрой"
    )
    
    await update.message.reply_text(
        role_text,
        reply_markup=get_role_keyboard(),
        parse_mode="HTML"
    )
    
    return ENTER_ROLE

async def process_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора роли"""
    user = update.effective_user
    role_text = update.message.text
    
    # Преобразуем текст роли в enum
    role_mapping = {
        "Игрок": UserRole.PLAYER,
        "Водитель": UserRole.DRIVER,
        "Наблюдатель": UserRole.OBSERVER
    }
    
    role = role_mapping.get(role_text, None)
    
    if role is None:
        await update.message.reply_text(
            "❌ Пожалуйста, выберите роль из предложенного списка:",
            reply_markup=get_role_keyboard()
        )
        return ENTER_ROLE
    
    # Сохраняем роль во временное хранилище
    context.user_data["role"] = role
    logger.info(f"Пользователь {user.id} выбрал роль: {role}")
    
    # Получаем правила из SettingsService и запрашиваем подтверждение
    rules = SettingsService.get_game_rules()
    rules_text = (
        f"✅ <b>Роль: {role_text}</b>\n\n"
        f"📋 <b>Правила игры PRYATON</b>\n\n"
        f"{rules}\n\n"
        f"⚠️ <b>Для завершения регистрации необходимо принять правила:</b>"
    )
    
    await update.message.reply_text(
        rules_text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML"
    )
    
    return CONFIRM_RULES

async def process_rules_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик подтверждения правил"""
    user = update.effective_user
    confirmation = update.message.text
    
    if confirmation != "✅ Да, согласен с правилами":
        # Пользователь не согласен с правилами
        logger.info(f"Пользователь {user.id} не согласился с правилами")
        
        reject_text = (
            "❌ <b>Регистрация отменена</b>\n\n"
            "К сожалению, вы не можете использовать бота без согласия с правилами.\n\n"
            "Если вы передумаете, нажмите /start для повторной регистрации."
        )
        
        await update.message.reply_text(
            reject_text,
            reply_markup=remove_keyboard(),
            parse_mode="HTML"
        )
        
        # Очищаем временное хранилище
        context.user_data.clear()
        
        return ConversationHandler.END
    
    # Пользователь согласился с правилами, завершаем регистрацию
    logger.info(f"Пользователь {user.id} согласился с правилами, завершаем регистрацию")
    
    # Получаем данные из временного хранилища
    name = context.user_data.get("name")
    phone = context.user_data.get("phone") 
    district = context.user_data.get("district")
    role = context.user_data.get("role")
    
    # Создаем пользователя в БД
    success = UserService.create_user(
        telegram_id=user.id,
        name=name,
        username=user.username,
        phone=phone,
        district=district,
        default_role=role
    )
    
    if not success:
        logger.error(f"Ошибка при создании пользователя {user.id}")
        await update.message.reply_text(
            "❌ Произошла ошибка при регистрации. Попробуйте еще раз позже.",
            reply_markup=remove_keyboard()
        )
        return ConversationHandler.END
    
    # Очищаем временное хранилище
    context.user_data.clear()
    
    # Завершаем регистрацию
    success_text = (
        f"🎉 <b>Поздравляем с регистрацией!</b>\n\n"
        f"✅ Вы успешно зарегистрировались в системе PRYATON.\n\n"
        f"🎮 Теперь вы можете:\n"
        f"• Записываться на игры\n"
        f"• Участвовать в играх по геолокации\n"
        f"• Общаться с другими игроками\n\n"
        f"🏠 Используйте главное меню для навигации!"
    )
    
    await update.message.reply_text(
        success_text,
        reply_markup=get_contextual_main_keyboard(user.id),
        parse_mode="HTML"
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена текущего диалога"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} отменил текущую операцию")
    
    cancel_text = (
        "❌ <b>Операция отменена</b>\n\n"
        "Нажмите 🏠 Главное меню для возврата к началу."
    )
    
    await update.message.reply_text(
        cancel_text,
        reply_markup=remove_keyboard(),
        parse_mode="HTML"
    )
    
    # Очищаем временное хранилище
    context.user_data.clear()
    
    return ConversationHandler.END 