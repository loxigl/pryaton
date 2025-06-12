import os
from typing import List, Optional
import pytz
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from datetime import datetime, timedelta, timezone

from src.models.base import get_db
from src.services.user_context_service import UserContextService
from src.services.user_service import UserService
from src.models.game import GameRole, GameStatus



DEFAULT_TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "Europe/Moscow"))

def format_msk_time(dt: datetime) -> str:
    """Форматирует время в МСК"""
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%H:%M')

def format_msk_datetime(dt: datetime) -> str:
    """Форматирует дату и время в МСК"""
    msk_time = dt.astimezone(DEFAULT_TIMEZONE)
    return msk_time.strftime('%d.%m.%Y %H:%M')

class DynamicKeyboardService:
    """Сервис для создания динамических контекстно-зависимых клавиатур"""
    
    def __init__(self):
        db_generator=get_db()
        self.db = next(db_generator)
    
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
        game_info = f"⏰ {game.district} в {format_msk_time(game.scheduled_at)}"
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

    def get_games_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Получает клавиатуру со списком игр"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем активные игры
            cursor.execute("""
                SELECT 
                    g.id,
                    g.district,
                    g.scheduled_at,
                    g.status,
                    g.max_participants,
                    COUNT(p.id) as participant_count,
                    SUM(CASE WHEN p.role = 'DRIVER' THEN 1 ELSE 0 END) as driver_count
                FROM games g
                LEFT JOIN participants p ON g.id = p.game_id
                WHERE g.status IN ('RECRUITING', 'UPCOMING', 'HIDING_PHASE', 'SEARCHING_PHASE')
                GROUP BY g.id
                ORDER BY g.scheduled_at DESC
            """)
            
            games = []
            for row in cursor.fetchall():
                games.append({
                    'id': row[0],
                    'district': row[1],
                    'scheduled_at': row[2],
                    'status': row[3],
                    'max_participants': row[4],
                    'participant_count': row[5] or 0,
                    'driver_count': row[6] or 0
                })
            
            # Формируем кнопки
            keyboard = []
            for game in games:
                status_emoji = {
                    'RECRUITING': '📝',
                    'UPCOMING': '⏳',
                    'HIDING_PHASE': '🏃',
                    'SEARCHING_PHASE': '🔍',
                    'FINISHED': '✅',
                    'CANCELLED': '❌'
                }.get(game['status'], '❓')
                
                button_text = (
                    f"{status_emoji} {game['district']} - "
                    f"{format_msk_datetime(game['scheduled_at'])} "
                    f"({game['participant_count']}/{game['max_participants']})"
                )
                
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"game_{game['id']}"
                    )
                ])
            
            return InlineKeyboardMarkup(keyboard)
    
    def get_game_details_keyboard(self, game_id: int, user_id: int) -> InlineKeyboardMarkup:
        """Получает клавиатуру с деталями игры"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем информацию об игре
            cursor.execute("""
                SELECT 
                    g.id,
                    g.district,
                    g.scheduled_at,
                    g.status,
                    g.max_participants,
                    COUNT(p.id) as participant_count,
                    SUM(CASE WHEN p.role = 'DRIVER' THEN 1 ELSE 0 END) as driver_count
                FROM games g
                LEFT JOIN participants p ON g.id = p.game_id
                WHERE g.id = ?
                GROUP BY g.id
            """, (game_id,))
            
            game = cursor.fetchone()
            if not game:
                return None
            
            # Формируем кнопки
            keyboard = []
            
            # Кнопка для присоединения/выхода
            is_participant = self._is_user_participant(game_id, user_id)
            if is_participant:
                keyboard.append([
                    InlineKeyboardButton(
                        "❌ Выйти из игры",
                        callback_data=f"leave_game_{game_id}"
                    )
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        "✅ Присоединиться",
                        callback_data=f"join_game_{game_id}"
                    )
                ])
            
            # Кнопка для просмотра участников
            keyboard.append([
                InlineKeyboardButton(
                    "👥 Участники",
                    callback_data=f"game_participants_{game_id}"
                )
            ])
            
            # Кнопка для просмотра фото
            keyboard.append([
                InlineKeyboardButton(
                    "📸 Фото",
                    callback_data=f"game_photos_{game_id}"
                )
            ])
            
            # Кнопка для возврата к списку игр
            keyboard.append([
                InlineKeyboardButton(
                    "« Назад к списку игр",
                    callback_data="back_to_games"
                )
            ])
            
            return InlineKeyboardMarkup(keyboard)
    
    def _is_user_participant(self, game_id: int, user_id: int) -> bool:
        """Проверяет, является ли пользователь участником игры"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 1
                FROM participants
                WHERE game_id = ? AND user_id = ?
            """, (game_id, user_id))
            
            return bool(cursor.fetchone()) 