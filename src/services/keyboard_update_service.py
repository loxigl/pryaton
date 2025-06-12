from loguru import logger
import asyncio
from typing import List
from telegram import Bot

from src.models.base import get_db
from src.models.user import User
from src.models.game import Game, GameParticipant
from src.keyboards.reply import get_contextual_main_keyboard

class KeyboardUpdateService:
    """Сервис для обновления клавиатуры у пользователей при изменении статуса игры"""
    
    @staticmethod
    def schedule_keyboard_updates_for_game(game_id: int) -> None:
        """Запланировать отправку сообщений для обновления клавиатур всем участникам игры"""
        try:
            # Получаем список участников игры
            db_generator = get_db()
            db = next(db_generator)
            
            participants = db.query(GameParticipant)\
                .filter(GameParticipant.game_id == game_id)\
                .all()
            
            if not participants:
                logger.warning(f"Нет участников для обновления клавиатур в игре {game_id}")
                return
            
            user_ids = []
            for participant in participants:
                user = db.query(User).filter(User.id == participant.user_id).first()
                if user and user.telegram_id:
                    user_ids.append(user.telegram_id)
            
            if user_ids:
                # Создаем асинхронную задачу для обновления клавиатур
                asyncio.create_task(KeyboardUpdateService._send_keyboard_updates(user_ids))
                logger.info(f"Запланировано обновление клавиатур для {len(user_ids)} участников игры {game_id}")
        except Exception as e:
            logger.error(f"Ошибка при планировании обновления клавиатур для игры {game_id}: {e}")
    
    @staticmethod
    async def _send_keyboard_updates(user_ids: List[int]) -> None:
        """Отправляет сообщения для обновления клавиатур пользователям"""
        try:
            # Импортируем бота
            from main import TOKEN
            bot = Bot(token=TOKEN)
            
            for user_id in user_ids:
                try:
                    # Получаем актуальную клавиатуру для пользователя
                    keyboard = get_contextual_main_keyboard(user_id)
                    
                    # Отправляем сообщение с новой клавиатурой
                    await bot.send_message(
                        chat_id=user_id,
                        text="🔄 <b>Игра началась или изменила статус!</b>\n\nОбновляем вашу клавиатуру для доступа к игровым функциям.",
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    
                    # Небольшая задержка между сообщениями
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Ошибка при отправке обновления клавиатуры пользователю {user_id}: {e}")
            
            logger.info(f"Отправлены обновления клавиатур {len(user_ids)} пользователям")
        except Exception as e:
            logger.error(f"Ошибка при отправке обновлений клавиатур: {e}") 