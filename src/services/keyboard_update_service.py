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
            logger.info(f"🔄 Начинаем планирование обновления клавиатур для игры {game_id}")
            
            # Получаем список участников игры
            db_generator = get_db()
            db = next(db_generator)
            
            participants = db.query(GameParticipant)\
                .filter(GameParticipant.game_id == game_id)\
                .all()
            
            logger.info(f"Найдено {len(participants)} участников в игре {game_id}")
            
            if not participants:
                logger.warning(f"Нет участников для обновления клавиатур в игре {game_id}")
                return
            
            user_ids = []
            for participant in participants:
                user = db.query(User).filter(User.id == participant.user_id).first()
                if user and user.telegram_id:
                    user_ids.append(user.telegram_id)
                    logger.debug(f"Добавлен пользователь {user.name} (telegram_id: {user.telegram_id}) для обновления клавиатуры")
                else:
                    logger.warning(f"Пользователь {participant.user_id} не найден или не имеет telegram_id")
            
            logger.info(f"Подготовлено {len(user_ids)} telegram_id для обновления клавиатур: {user_ids}")
            
            if user_ids:
                # Используем планировщик для отправки обновлений
                logger.info("Получаем планировщик для отправки обновлений клавиатур")
                from src.services.enhanced_scheduler_service import get_enhanced_scheduler
                scheduler = get_enhanced_scheduler()
                
                if scheduler and scheduler.bot:
                    logger.info("Планируем задачу обновления клавиатур через планировщик")
                    # Используем планировщик для создания задачи
                    from datetime import datetime, timedelta
                    
                    # Планируем задачу на выполнение немедленно (через 1 секунду)
                    run_time = datetime.now() + timedelta(seconds=1)
                    
                    scheduler.scheduler.add_job(
                        scheduler.send_keyboard_updates,  # Используем метод планировщика
                        trigger='date',
                        run_date=run_time,
                        args=[user_ids, game_id],
                        id=f"keyboard_update_{game_id}_{int(run_time.timestamp())}",
                        replace_existing=True
                    )
                    logger.info(f"Запланировано обновление клавиатур для {len(user_ids)} участников игры {game_id} на {run_time}")
                else:
                    logger.error("Не удалось получить планировщик или бот для обновления клавиатур")
                    logger.error(f"scheduler: {scheduler}, scheduler.bot: {getattr(scheduler, 'bot', 'НЕТ АТРИБУТА')}")
            else:
                logger.warning(f"Не найдено действительных telegram_id для обновления клавиатур в игре {game_id}")
                
        except Exception as e:
            logger.error(f"Ошибка при планировании обновления клавиатур для игры {game_id}: {e}")
            import traceback
            logger.error(f"Полный трейс ошибки: {traceback.format_exc()}")
    
    @staticmethod
    async def _send_keyboard_updates_sync(user_ids: List[int], bot: Bot) -> None:
        """Устаревший метод - оставлен для совместимости"""
        try:
            logger.info(f"🚀 (УСТАРЕВШИЙ МЕТОД) Начинаем отправку обновлений клавиатур для {len(user_ids)} пользователей")
            
            logger.info(f"Используем бот: {bot}")
            
            sent_count = 0
            for user_id in user_ids:
                try:
                    logger.info(f"Обрабатываем пользователя {user_id}")
                    
                    # Получаем актуальную клавиатуру для пользователя
                    keyboard = get_contextual_main_keyboard(user_id)
                    logger.info(f"Получена клавиатура для пользователя {user_id}: {len(keyboard.keyboard)} рядов")
                    
                    # Отправляем сообщение с новой клавиатурой
                    logger.info(f"Отправляем сообщение пользователю {user_id}")
                    message = await bot.send_message(
                        chat_id=user_id,
                        text="🔄 <b>Игра началась или изменила статус!</b>\n\nОбновляем вашу клавиатуру для доступа к игровым функциям.",
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    logger.info(f"Сообщение отправлено пользователю {user_id}, message_id: {message.message_id}")
                    sent_count += 1
                    
                    # Небольшая задержка между сообщениями
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Ошибка при отправке обновления клавиатуры пользователю {user_id}: {e}")
                    import traceback
                    logger.error(f"Трейс ошибки для пользователя {user_id}: {traceback.format_exc()}")
            
            logger.info(f"✅ Отправлены обновления клавиатур {sent_count}/{len(user_ids)} пользователям")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке обновлений клавиатур: {e}")
            import traceback
            logger.error(f"Полный трейс ошибки отправки: {traceback.format_exc()}")
    
    @staticmethod
    async def _send_keyboard_updates(user_ids: List[int], bot: Bot) -> None:
        """Устаревший метод - оставлен для совместимости"""
        return await KeyboardUpdateService._send_keyboard_updates_sync(user_ids, bot) 