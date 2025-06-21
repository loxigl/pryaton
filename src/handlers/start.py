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
ENTER_NAME, ENTER_PHONE, ENTER_DISTRICT, ENTER_ROLE, ENTER_CAR_BRAND, ENTER_CAR_COLOR, ENTER_CAR_NUMBER, CONFIRM_RULES = range(8)

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
        # Проверяем заполненность новых полей автомобиля
        if not db_user.car_brand or not db_user.car_color or not db_user.car_number:
            context.user_data["name"] = db_user.name
            context.user_data["phone"] = db_user.phone
            context.user_data["district"] = db_user.district
            context.user_data["role"] = db_user.default_role
            if not db_user.car_brand:
                car_brand_text = (
                    f"🚗 <b>Укажите марку автомобиля</b>\nВведите название марки вашего автомобиля (например, Toyota, BMW и т.д.)."
                )
                keyboard = ReplyKeyboardMarkup([
                    ["⬅️ Назад"],
                    ["❌ Отмена"]
                ], resize_keyboard=True)
                await update.message.reply_text(
                    car_brand_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return ENTER_CAR_BRAND
            elif not db_user.car_color:
                car_color_text = (
                    f"🎨 <b>Укажите цвет автомобиля</b>\nВведите цвет вашего автомобиля (например, белый, черный, красный и т.д.)."
                )
                keyboard = ReplyKeyboardMarkup([
                    ["⬅️ Назад"],
                    ["❌ Отмена"]
                ], resize_keyboard=True)
                await update.message.reply_text(
                    car_color_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return ENTER_CAR_COLOR
            elif not db_user.car_number:
                car_number_text = (
                    f"🔢 <b>Укажите государственный номер автомобиля</b>\nВведите гос. номер вашего автомобиля (например, А123БВ777)."
                )
                keyboard = ReplyKeyboardMarkup([
                    ["⬅️ Назад"],
                    ["❌ Отмена"]
                ], resize_keyboard=True)
                await update.message.reply_text(
                    car_number_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return ENTER_CAR_NUMBER
        
        # Очищаем контекст игры при нажатии на главное меню
        
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
    
    # Создаем клавиатуру с кнопкой назад
    keyboard = get_phone_keyboard()
    
    await update.message.reply_text(
        phone_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ENTER_PHONE

async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода номера телефона"""
    user = update.effective_user
    phone = None
    
    # Проверка на кнопку "Назад"
    if update.message.text == "⬅️ Назад":
        # Возвращаемся к вводу имени
        welcome_text = (
            f"👋 <b>Привет!</b>\n\n"
            f"📝 <b>Как вас зовут?</b>\n"
            f"(Введите имя или ник, который будет виден другим участникам)"
        )
        
        await update.message.reply_text(
            welcome_text,
            parse_mode="HTML"
        )
        return ENTER_NAME
    
    if update.message.text == "➡️ Пропустить":
        logger.info(f"Пользователь {user.id} пропустил ввод телефона")
    elif update.message.contact:
        phone = update.message.contact.phone_number
        logger.info(f"Пользователь {user.id} предоставил контакт: {phone}")
    elif update.message.text:
        # Простая проверка на корректность номера
        phone_text = update.message.text.strip()
        if not phone_text.startswith("+") and not phone_text.isdigit():
            await update.message.reply_text(
                "❌ Некорректный формат номера. Попробуйте еще раз или пропустите этот шаг:",
                reply_markup=get_phone_keyboard()
            )
            return ENTER_PHONE
        phone = phone_text
        logger.info(f"Пользователь {user.id} ввел телефон вручную: {phone}")
    
    # Сохраняем телефон во временное хранилище
    context.user_data["phone"] = phone
    
    # Запрашиваем район
    district_text = (
        f"✅ <b>{f'Телефон: {phone}' if phone else 'Телефон: не указан'}</b>\n\n"
        f"🏙 <b>Выберите район</b>\n"
        f"Это поможет с подбором ближайших игр."
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
    
    # Проверка на кнопку "Назад"
    if update.message.text == "⬅️ Назад":
        # Возвращаемся к вводу телефона
        phone_text = (
            f"✅ <b>Отлично, {context.user_data['name']}!</b>\n\n"
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
    
    # Проверяем, что выбран валидный район
    available_districts = SettingsService.get_districts()
    if district not in available_districts and district != "❌ Отмена":
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
        f"Это ваша предпочитаемая роль в играх"
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
    
    # Проверка на кнопку "Назад"
    if update.message.text == "⬅️ Назад":
        # Возвращаемся к выбору района
        district_text = (
            f"✅ <b>Телефон: {context.user_data.get('phone') or 'не указан'}</b>\n\n"
            f"🏙 <b>Выберите район</b>\n"
            f"Это поможет с подбором ближайших игр."
        )
        
        await update.message.reply_text(
            district_text,
            reply_markup=get_district_keyboard(),
            parse_mode="HTML"
        )
        return ENTER_DISTRICT
    
    # Получаем роль из отображаемого имени
    role = SettingsService.get_role_from_display_name(role_text)
    
    if role is None and role_text != "❌ Отмена":
        await update.message.reply_text(
            "❌ Пожалуйста, выберите роль из предложенного списка:",
            reply_markup=get_role_keyboard()
        )
        return ENTER_ROLE
    
    # Сохраняем роль во временное хранилище
    context.user_data["role"] = role
    logger.info(f"Пользователь {user.id} выбрал роль: {role}")
    
    # Запрашиваем данные об автомобиле
    car_brand_text = (
        f"✅ <b>Роль: {role_text}</b>\n\n"
        f"🚗 <b>Укажите марку автомобиля</b>\n"
        f"Введите название марки вашего автомобиля (например, Toyota, BMW и т.д.)."
    )
    
    # Создаем клавиатуру с кнопкой назад
    keyboard = ReplyKeyboardMarkup([
        ["⬅️ Назад"],
        ["❌ Отмена"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        car_brand_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ENTER_CAR_BRAND

async def process_car_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода марки автомобиля"""
    user = update.effective_user
    car_brand = update.message.text
    
    # Проверка на кнопку "Назад"
    if update.message.text == "⬅️ Назад":
        # Возвращаемся к выбору роли
        role_text = (
            f"✅ <b>Район: {context.user_data['district']}</b>\n\n"
            f"🎭 <b>Выберите роль по умолчанию</b>\n"
            f"Это ваша предпочитаемая роль в играх"
        )
        
        await update.message.reply_text(
            role_text,
            reply_markup=get_role_keyboard(),
            parse_mode="HTML"
        )
        return ENTER_ROLE
    
    if car_brand == "❌ Отмена":
        await update.message.reply_text(
            "❌ Регистрация отменена. Начните снова, отправив команду /start",
            reply_markup=remove_keyboard()
        )
        return ConversationHandler.END
    
    # Проверяем валидность марки автомобиля
    if len(car_brand.strip()) < 2:
        await update.message.reply_text(
            "❌ Марка автомобиля должна содержать минимум 2 символа. Попробуйте еще раз:"
        )
        return ENTER_CAR_BRAND
    
    if len(car_brand) > 50:
        await update.message.reply_text(
            "❌ Марка автомобиля слишком длинная (максимум 50 символов). Попробуйте еще раз:"
        )
        return ENTER_CAR_BRAND
    
    # Сохраняем марку автомобиля во временное хранилище
    context.user_data["car_brand"] = car_brand.strip()
    logger.info(f"Пользователь {user.id} ввел марку автомобиля: {car_brand}")
    
    # Запрашиваем цвет автомобиля
    car_color_text = (
        f"✅ <b>Марка автомобиля: {car_brand}</b>\n\n"
        f"🎨 <b>Укажите цвет автомобиля</b>\n"
        f"Введите цвет вашего автомобиля (например, белый, черный, красный и т.д.)."
    )
    
    # Создаем клавиатуру с кнопкой назад
    keyboard = ReplyKeyboardMarkup([
        ["⬅️ Назад"],
        ["❌ Отмена"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        car_color_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ENTER_CAR_COLOR

async def process_car_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода цвета автомобиля"""
    user = update.effective_user
    car_color = update.message.text
    
    # Проверка на кнопку "Назад"
    if update.message.text == "⬅️ Назад":
        # Возвращаемся к вводу марки автомобиля
        car_brand_text = (
            f"✅ <b>Роль: {context.user_data['role']}</b>\n\n"
            f"🚗 <b>Укажите марку автомобиля</b>\n"
            f"Введите название марки вашего автомобиля (например, Toyota, BMW и т.д.)."
        )
        
        keyboard = ReplyKeyboardMarkup([
            ["⬅️ Назад"],
            ["❌ Отмена"]
        ], resize_keyboard=True)
        
        await update.message.reply_text(
            car_brand_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return ENTER_CAR_BRAND
    
    if car_color == "❌ Отмена":
        await update.message.reply_text(
            "❌ Регистрация отменена. Начните снова, отправив команду /start",
            reply_markup=remove_keyboard()
        )
        return ConversationHandler.END
    
    # Проверяем валидность цвета автомобиля
    if len(car_color.strip()) < 2:
        await update.message.reply_text(
            "❌ Цвет автомобиля должен содержать минимум 2 символа. Попробуйте еще раз:"
        )
        return ENTER_CAR_COLOR
    
    if len(car_color) > 30:
        await update.message.reply_text(
            "❌ Цвет автомобиля слишком длинный (максимум 30 символов). Попробуйте еще раз:"
        )
        return ENTER_CAR_COLOR
    
    # Сохраняем цвет автомобиля во временное хранилище
    context.user_data["car_color"] = car_color.strip()
    logger.info(f"Пользователь {user.id} ввел цвет автомобиля: {car_color}")
    
    # Запрашиваем гос. номер автомобиля
    car_number_text = (
        f"✅ <b>Цвет автомобиля: {car_color}</b>\n\n"
        f"🔢 <b>Укажите государственный номер автомобиля</b>\n"
        f"Введите гос. номер вашего автомобиля (например, А123БВ777)."
    )
    
    # Создаем клавиатуру с кнопкой назад
    keyboard = ReplyKeyboardMarkup([
        ["⬅️ Назад"],
        ["❌ Отмена"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        car_number_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ENTER_CAR_NUMBER

async def process_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода гос. номера автомобиля"""
    user = update.effective_user
    car_number = update.message.text
    
    # Проверка на кнопку "Назад"
    if update.message.text == "⬅️ Назад":
        # Возвращаемся к вводу цвета автомобиля
        car_color_text = (
            f"✅ <b>Марка автомобиля: {context.user_data['car_brand']}</b>\n\n"
            f"🎨 <b>Укажите цвет автомобиля</b>\n"
            f"Введите цвет вашего автомобиля (например, белый, черный, красный и т.д.)."
        )
        
        keyboard = ReplyKeyboardMarkup([
            ["⬅️ Назад"],
            ["❌ Отмена"]
        ], resize_keyboard=True)
        
        await update.message.reply_text(
            car_color_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return ENTER_CAR_COLOR
    
    if car_number == "❌ Отмена":
        await update.message.reply_text(
            "❌ Регистрация отменена. Начните снова, отправив команду /start",
            reply_markup=remove_keyboard()
        )
        return ConversationHandler.END
    
    # Проверяем валидность гос. номера автомобиля
    if len(car_number.strip()) < 5:
        await update.message.reply_text(
            "❌ Гос. номер автомобиля должен содержать минимум 5 символов. Попробуйте еще раз:"
        )
        return ENTER_CAR_NUMBER
    
    if len(car_number) > 20:
        await update.message.reply_text(
            "❌ Гос. номер автомобиля слишком длинный (максимум 20 символов). Попробуйте еще раз:"
        )
        return ENTER_CAR_NUMBER
    
    # Сохраняем гос. номер автомобиля во временное хранилище
    context.user_data["car_number"] = car_number.strip()
    logger.info(f"Пользователь {user.id} ввел гос. номер автомобиля: {car_number}")
    
    # Получаем правила из SettingsService и запрашиваем подтверждение
    rules = SettingsService.get_game_rules()
    rules_text = (
        f"✅ <b>Автомобиль:</b> {context.user_data['car_brand']} {context.user_data['car_color']}, номер {context.user_data['car_number']}\n\n"
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
    # Проверка на кнопку "Назад"
    if update.message.text == "⬅️ Назад":
        # Возвращаемся к вводу гос. номера автомобиля
        car_number_text = (
            f"✅ <b>Цвет автомобиля: {context.user_data['car_color']}</b>\n\n"
            f"🔢 <b>Укажите государственный номер автомобиля</b>\n"
            f"Введите гос. номер вашего автомобиля (например, А123БВ777)."
        )
        keyboard = ReplyKeyboardMarkup([
            ["⬅️ Назад"],
            ["❌ Отмена"]
        ], resize_keyboard=True)
        await update.message.reply_text(
            car_number_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return ENTER_CAR_NUMBER
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
        context.user_data.clear()
        return ConversationHandler.END
    logger.info(f"Пользователь {user.id} согласился с правилами, завершаем регистрацию")
    # Получаем данные из временного хранилища
    name = context.user_data.get("name")
    phone = context.user_data.get("phone") 
    district = context.user_data.get("district")
    role = context.user_data.get("role")
    car_brand = context.user_data.get("car_brand")
    car_color = context.user_data.get("car_color")
    car_number = context.user_data.get("car_number")
    # Проверяем, есть ли пользователь в базе
    db_generator = get_db()
    db = next(db_generator)
    db_user = db.query(User).filter(User.telegram_id == user.id).first()
    if db_user:
        # Обновляем только недостающие поля
        update_fields = {}
        if not db_user.car_brand:
            update_fields["car_brand"] = car_brand
        if not db_user.car_color:
            update_fields["car_color"] = car_color
        if not db_user.car_number:
            update_fields["car_number"] = car_number
        # Можно обновить и другие поля, если нужно
        UserService.update_user(db_user.id, **update_fields)
        logger.info(f"Пользователь {user.id} обновил недостающие поля профиля")
    else:
        # Создаём нового пользователя
        success = UserService.create_user(
            telegram_id=user.id,
            name=name,
            username=user.username,
            phone=phone,
            district=district,
            default_role=role,
            car_brand=car_brand,
            car_color=car_color,
            car_number=car_number
        )
        if not success:
            logger.error(f"Ошибка при создании пользователя {user.id}")
            await update.message.reply_text(
                "❌ Произошла ошибка при регистрации. Попробуйте еще раз позже.",
                reply_markup=remove_keyboard()
            )
            return ConversationHandler.END
    context.user_data.clear()
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
    """Обработчик отмены регистрации"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} отменил регистрацию")
    
    await update.message.reply_text(
        "❌ Регистрация отменена. Начните снова, отправив команду /start",
        reply_markup=remove_keyboard()
    )
    
    # Очищаем временное хранилище
    context.user_data.clear()
    
    return ConversationHandler.END 