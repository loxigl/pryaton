from typing import List, Optional
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger

from src.services.user_context_service import UserContextService
from src.services.user_service import UserService
from src.models.game import GameRole, GameStatus

class DynamicKeyboardService:
    """Сервис для создания динамических контекстно-зависимых клавиатур"""
    
    @staticmethod
    def get_contextual_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
        """Получить главную клавиатуру в зависимости от контекста пользователя"""
        try:
            context = UserContextService.get_user_game_context(user_id)
            is_admin = UserService.is_admin(user_id)
            
            if context.status == UserContextService.STATUS_NORMAL:
                return DynamicKeyboardService._get_normal_keyboard(is_admin)
            elif context.status == UserContextService.STATUS_REGISTERED:
                return DynamicKeyboardService._get_registered_keyboard(is_admin, context.game)
            elif context.status == UserContextService.STATUS_IN_GAME:
                return DynamicKeyboardService._get_in_game_keyboard(is_admin, context.game, context.participant)
            elif context.status == UserContextService.STATUS_GAME_FINISHED:
                return DynamicKeyboardService._get_finished_game_keyboard(is_admin, context.game)
            else:
                return DynamicKeyboardService._get_normal_keyboard(is_admin)
                
        except Exception as e:
            logger.error(f"Ошибка при создании контекстной клавиатуры для пользователя {user_id}: {e}")
            # Возвращаем базовую клавиатуру при ошибке
            return DynamicKeyboardService._get_normal_keyboard(UserService.is_admin(user_id))
    
    @staticmethod
    def _get_normal_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
        """Стандартная клавиатура для пользователя без активных игр"""
        buttons = [
            [KeyboardButton(text="🎮 Доступные игры"), KeyboardButton(text="🎯 Мои игры")],
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="ℹ️ Помощь")]
        ]
        
        if is_admin:
            buttons.append([KeyboardButton(text="🔑 Админ-панель"), KeyboardButton(text="📊 Мониторинг")])
            buttons.append([KeyboardButton(text="📅 События планировщика")])
        
        buttons.append([KeyboardButton(text="🏠 Главное меню")])
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    @staticmethod
    def _get_registered_keyboard(is_admin: bool, game) -> ReplyKeyboardMarkup:
        """Клавиатура для пользователя, записанного на игру"""
        buttons = [
            [KeyboardButton(text="🎮 Моя игра"), KeyboardButton(text="🎯 Все мои игры")],
            [KeyboardButton(text="🎲 Доступные игры"), KeyboardButton(text="👤 Мой профиль")]
        ]
        
        # Добавляем информацию о предстоящей игре
        game_info = f"⏰ {game.district} в {game.scheduled_at.strftime('%H:%M')}"
        buttons.insert(0, [KeyboardButton(text=game_info)])
        
        if is_admin:
            buttons.append([KeyboardButton(text="🔑 Админ-панель"), KeyboardButton(text="📊 Мониторинг")])
        
        buttons.append([KeyboardButton(text="🏠 Главное меню")])
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    @staticmethod
    def _get_in_game_keyboard(is_admin: bool, game, participant) -> ReplyKeyboardMarkup:
        """Клавиатура для пользователя в активной игре"""
        role = participant.role if participant else None
        
        if role == GameRole.DRIVER:
            buttons = DynamicKeyboardService._get_driver_game_buttons(game)
        elif role == GameRole.SEEKER:
            buttons = DynamicKeyboardService._get_seeker_game_buttons(game)
        else:
            # Роль еще не назначена или неизвестна
            buttons = [
                [KeyboardButton(text="🎮 Статус игры"), KeyboardButton(text="⏰ Ожидание роли")]
            ]
        
        # Общие кнопки для всех ролей в игре
        buttons.append([KeyboardButton(text="📊 Моя игра"), KeyboardButton(text="ℹ️ Правила")])
        
        if is_admin:
            buttons.append([KeyboardButton(text="🔑 Админ-панель")])
        
        buttons.append([KeyboardButton(text="🏠 Главное меню")])
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    @staticmethod
    def _get_driver_game_buttons(game) -> List[List[KeyboardButton]]:
        """Кнопки для водителя в зависимости от фазы игры"""
        if game.status in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
            # В процессе игры - водитель может отправлять локацию и фото
            return [
                [KeyboardButton(text="📍 Отправить локацию"), KeyboardButton(text="📸 Фото места")],
                [KeyboardButton(text="🚗 Меня нашли"), KeyboardButton(text="⚠️ Нужна помощь")]
            ]
        else:
            return [
                [KeyboardButton(text="🎮 Статус игры"), KeyboardButton(text="⏰ Ожидание старта")]
            ]
    
    @staticmethod
    def _get_seeker_game_buttons(game) -> List[List[KeyboardButton]]:
        """Кнопки для искателя в зависимости от фазы игры"""
        if game.status in [GameStatus.HIDING_PHASE, GameStatus.SEARCHING_PHASE]:
            # В процессе игры - искатель может отправлять локацию и фото находки
            return [
                [KeyboardButton(text="📍 Моя позиция"), KeyboardButton(text="📸 Фото находки")],
                [KeyboardButton(text="🔍 Я нашел водителя"), KeyboardButton(text="⚠️ Нужна помощь")]
            ]
        else:
            return [
                [KeyboardButton(text="🎮 Статус игры"), KeyboardButton(text="⏰ Ожидание старта")]
            ]
    
    @staticmethod
    def _get_finished_game_keyboard(is_admin: bool, game) -> ReplyKeyboardMarkup:
        """Клавиатура для пользователя после завершения игры"""
        buttons = [
            [KeyboardButton(text="📊 Результаты игры"), KeyboardButton(text="🏆 Мои достижения")],
            [KeyboardButton(text="🎮 Новые игры"), KeyboardButton(text="🎯 Все мои игры")],
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="ℹ️ Помощь")]
        ]
        
        if is_admin:
            buttons.append([KeyboardButton(text="🔑 Админ-панель"), KeyboardButton(text="📊 Мониторинг")])
        
        buttons.append([KeyboardButton(text="🏠 Главное меню")])
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    @staticmethod
    def get_game_action_inline_keyboard(game_id: int, user_id: int) -> InlineKeyboardMarkup:
        """Получить inline клавиатуру для быстрых действий в игре"""
        context = UserContextService.get_user_game_context(user_id)
        
        if context.status != UserContextService.STATUS_IN_GAME:
            return InlineKeyboardMarkup([])
        
        buttons = []
        role = context.participant.role if context.participant else None
        
        if role == GameRole.DRIVER:
            buttons = [
                [InlineKeyboardButton("📍 Отправить локацию", callback_data=f"send_location_{game_id}")],
                [InlineKeyboardButton("📸 Сделать фото места", callback_data=f"photo_place_{game_id}")],
                [InlineKeyboardButton("🚗 Меня нашли", callback_data=f"found_driver_{game_id}")],
            ]
        elif role == GameRole.SEEKER:
            buttons = [
                [InlineKeyboardButton("📍 Моя позиция", callback_data=f"send_location_{game_id}")],
                [InlineKeyboardButton("📸 Фото находки", callback_data=f"photo_find_{game_id}")],
                [InlineKeyboardButton("🔍 Нашел водителя", callback_data=f"found_seeker_{game_id}")],
            ]
        
        # Общие кнопки
        buttons.extend([
            [InlineKeyboardButton("📊 Статус игры", callback_data=f"game_status_{game_id}")],
            [InlineKeyboardButton("⚠️ Помощь", callback_data=f"game_help_{game_id}")]
        ])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def should_update_keyboard(user_id: int, current_keyboard_type: str) -> bool:
        """Проверить, нужно ли обновить клавиатуру пользователя"""
        context = UserContextService.get_user_game_context(user_id)
        
        # Маппинг статусов на типы клавиатур
        status_to_keyboard = {
            UserContextService.STATUS_NORMAL: "normal",
            UserContextService.STATUS_REGISTERED: "registered", 
            UserContextService.STATUS_IN_GAME: "in_game",
            UserContextService.STATUS_GAME_FINISHED: "finished"
        }
        
        expected_keyboard = status_to_keyboard.get(context.status, "normal")
        return current_keyboard_type != expected_keyboard 