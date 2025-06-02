from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import func, desc
from loguru import logger

from src.models.base import get_db
from src.models.game import Game, GameStatus, GameParticipant, GameRole, Location, Photo
from src.models.user import User


class MonitoringService:
    """Сервис для мониторинга и статистики игр"""
    
    @staticmethod
    def get_active_games_stats() -> Dict[str, Any]:
        """Получение статистики по активным играм"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Подсчет игр по статусам
            games_by_status = {}
            for status in GameStatus:
                count = db.query(Game).filter(Game.status == status).count()
                games_by_status[status.value] = count
            
            # Активные игры (в процессе или скоро)
            active_games = db.query(Game).filter(
                Game.status.in_([GameStatus.IN_PROGRESS, GameStatus.UPCOMING])
            ).all()
            
            # Игры сегодня
            today = datetime.now().date()
            today_games = db.query(Game).filter(
                func.date(Game.scheduled_at) == today
            ).all()
            
            # Общая статистика
            total_participants = db.query(GameParticipant).count()
            unique_players = db.query(GameParticipant.user_id).distinct().count()
            
            return {
                "games_by_status": games_by_status,
                "active_games_count": len(active_games),
                "today_games_count": len(today_games),
                "total_participants": total_participants,
                "unique_players": unique_players,
                "active_games": [
                    {
                        "id": game.id,
                        "district": game.district,
                        "scheduled_at": game.scheduled_at,
                        "status": game.status.value,
                        "participants": len(game.participants),
                        "max_participants": game.max_participants
                    }
                    for game in active_games
                ]
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики активных игр: {e}")
            return {}
    
    @staticmethod
    def get_game_detailed_info(game_id: int) -> Optional[Dict[str, Any]]:
        """Получение детальной информации об игре"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            game = db.query(Game).filter(Game.id == game_id).first()
            if not game:
                return None
            
            # Участники с их ролями
            participants_info = []
            for participant in game.participants:
                user = db.query(User).filter(User.id == participant.user_id).first()
                if user:
                    # Последняя геолокация
                    latest_location = db.query(Location).filter(
                        Location.user_id == user.id,
                        Location.game_id == game_id
                    ).order_by(Location.timestamp.desc()).first()
                    
                    # Количество фотографий
                    photos_count = db.query(Photo).filter(
                        Photo.user_id == user.id,
                        Photo.game_id == game_id
                    ).count()
                    
                    participants_info.append({
                        "user_id": user.id,
                        "name": user.name,
                        "username": user.username,
                        "role": participant.role.value if participant.role else "Не назначена",
                        "is_found": participant.is_found,
                        "found_at": participant.found_at,
                        "has_location": latest_location is not None,
                        "last_location_time": latest_location.timestamp if latest_location else None,
                        "photos_count": photos_count
                    })
            
            return {
                "game": {
                    "id": game.id,
                    "district": game.district,
                    "status": game.status.value,
                    "scheduled_at": game.scheduled_at,
                    "started_at": game.started_at,
                    "ended_at": game.ended_at,
                    "max_participants": game.max_participants,
                    "max_drivers": game.max_drivers,
                    "description": game.description
                },
                "participants": participants_info,
                "summary": {
                    "total_participants": len(participants_info),
                    "drivers_count": len([p for p in participants_info if p["role"] == "driver"]),
                    "seekers_count": len([p for p in participants_info if p["role"] == "seeker"]),
                    "found_drivers": len([p for p in participants_info if p["role"] == "driver" and p["is_found"]]),
                    "participants_with_location": len([p for p in participants_info if p["has_location"]]),
                    "total_photos": sum(p["photos_count"] for p in participants_info)
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения детальной информации об игре {game_id}: {e}")
            return None
    
    @staticmethod
    def get_player_statistics(user_id: Optional[int] = None, limit: int = 10) -> Dict[str, Any]:
        """Получение статистики игроков"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            if user_id:
                # Статистика конкретного игрока
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return {}
                
                participations = db.query(GameParticipant).filter(
                    GameParticipant.user_id == user_id
                ).all()
                
                games_count = len(participations)
                driver_games = len([p for p in participations if p.role == GameRole.DRIVER])
                seeker_games = len([p for p in participations if p.role == GameRole.SEEKER])
                wins_as_driver = len([p for p in participations if p.role == GameRole.DRIVER and not p.is_found])
                wins_as_seeker = len([p for p in participations if p.role == GameRole.SEEKER and p.is_found])
                
                return {
                    "user": {
                        "id": user.id,
                        "name": user.name,
                        "username": user.username,
                        "district": user.district
                    },
                    "stats": {
                        "total_games": games_count,
                        "driver_games": driver_games,
                        "seeker_games": seeker_games,
                        "wins_as_driver": wins_as_driver,
                        "wins_as_seeker": wins_as_seeker,
                        "win_rate_driver": wins_as_driver / driver_games if driver_games > 0 else 0,
                        "win_rate_seeker": wins_as_seeker / seeker_games if seeker_games > 0 else 0
                    }
                }
            else:
                # Топ игроков
                top_players = db.query(
                    User.id,
                    User.name,
                    User.username,
                    func.count(GameParticipant.id).label('games_count')
                ).join(
                    GameParticipant, User.id == GameParticipant.user_id
                ).group_by(
                    User.id, User.name, User.username
                ).order_by(
                    desc('games_count')
                ).limit(limit).all()
                
                return {
                    "top_players": [
                        {
                            "user_id": player.id,
                            "name": player.name,
                            "username": player.username,
                            "games_count": player.games_count
                        }
                        for player in top_players
                    ]
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики игроков: {e}")
            return {}
    
    @staticmethod
    def get_district_statistics() -> Dict[str, Any]:
        """Получение статистики по районам"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            # Игры по районам
            district_games = db.query(
                Game.district,
                func.count(Game.id).label('games_count')
            ).group_by(Game.district).order_by(desc('games_count')).all()
            
            # Игроки по районам
            district_players = db.query(
                User.district,
                func.count(User.id).label('players_count')
            ).group_by(User.district).order_by(desc('players_count')).all()
            
            return {
                "games_by_district": [
                    {
                        "district": district.district,
                        "games_count": district.games_count
                    }
                    for district in district_games
                ],
                "players_by_district": [
                    {
                        "district": district.district,
                        "players_count": district.players_count
                    }
                    for district in district_players
                ]
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики по районам: {e}")
            return {}
    
    @staticmethod
    def get_recent_activities(limit: int = 20) -> List[Dict[str, Any]]:
        """Получение последних активностей в системе"""
        try:
            db_generator = get_db()
            db = next(db_generator)
            
            activities = []
            
            # Последние созданные игры
            recent_games = db.query(Game).order_by(desc(Game.created_at)).limit(limit // 2).all()
            for game in recent_games:
                activities.append({
                    "type": "game_created",
                    "timestamp": game.created_at,
                    "description": f"Создана игра в районе {game.district}",
                    "game_id": game.id
                })
            
            # Последние регистрации на игры
            recent_participations = db.query(GameParticipant).join(
                Game, GameParticipant.game_id == Game.id
            ).join(
                User, GameParticipant.user_id == User.id
            ).order_by(desc(GameParticipant.id)).limit(limit // 2).all()
            
            for participation in recent_participations:
                # Используем created_at игры если joined_at недоступен
                timestamp = participation.joined_at if hasattr(participation, 'joined_at') and participation.joined_at else participation.game.created_at
                activities.append({
                    "type": "game_joined",
                    "timestamp": timestamp,
                    "description": f"{participation.user.name} записался на игру в {participation.game.district}",
                    "game_id": participation.game_id,
                    "user_id": participation.user_id
                })
            
            # Фильтруем активности с валидными timestamp и сортируем по времени
            valid_activities = [activity for activity in activities if activity["timestamp"] is not None]
            valid_activities.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return valid_activities[:limit]
            
        except Exception as e:
            logger.error(f"Ошибка получения последних активностей: {e}")
            return []
    
    @staticmethod
    def generate_game_report(game_id: int) -> Optional[str]:
        """Генерация отчета по игре"""
        try:
            game_info = MonitoringService.get_game_detailed_info(game_id)
            if not game_info:
                return None
            
            game = game_info["game"]
            participants = game_info["participants"]
            summary = game_info["summary"]
            
            report = f"""
📊 <b>ОТЧЕТ ПО ИГРЕ #{game['id']}</b>

🎮 <b>Основная информация:</b>
• Район: {game['district']}
• Статус: {game['status']}
• Запланировано: {game['scheduled_at'].strftime('%d.%m.%Y в %H:%M')}
"""
            
            if game['started_at']:
                report += f"• Начато: {game['started_at'].strftime('%d.%m.%Y в %H:%M')}\n"
            
            if game['ended_at']:
                report += f"• Завершено: {game['ended_at'].strftime('%d.%m.%Y в %H:%M')}\n"
                
                if game['started_at'] and game['ended_at']:
                    duration = game['ended_at'] - game['started_at']
                    hours, remainder = divmod(duration.total_seconds(), 3600)
                    minutes = remainder // 60
                    report += f"• Длительность: {int(hours):02d}:{int(minutes):02d}\n"
            
            report += f"""
👥 <b>Участники ({summary['total_participants']}):</b>
• Водители: {summary['drivers_count']} (найдено: {summary['found_drivers']})
• Искатели: {summary['seekers_count']}
• С геолокацией: {summary['participants_with_location']}
• Всего фото: {summary['total_photos']}

📋 <b>Список участников:</b>
"""
            
            for participant in participants:
                status_emoji = "✅" if participant['is_found'] else "❌"
                location_emoji = "📍" if participant['has_location'] else "📍❌"
                
                report += f"• {participant['name']} ({participant['role']}) {status_emoji} {location_emoji}\n"
                
                if participant['found_at']:
                    report += f"  Найден: {participant['found_at'].strftime('%H:%M')}\n"
                
                if participant['photos_count'] > 0:
                    report += f"  Фото: {participant['photos_count']}\n"
            
            if game['status'] == 'completed':
                drivers_found = [p for p in participants if p['role'] == 'driver' and p['is_found']]
                drivers_not_found = [p for p in participants if p['role'] == 'driver' and not p['is_found']]
                
                if drivers_not_found:
                    report += f"\n🏆 <b>Победители (не найденные водители):</b>\n"
                    for driver in drivers_not_found:
                        report += f"• {driver['name']}\n"
                
                if drivers_found:
                    report += f"\n🔍 <b>Найденные водители:</b>\n"
                    for driver in drivers_found:
                        report += f"• {driver['name']}"
                        if driver['found_at']:
                            report += f" (найден в {driver['found_at'].strftime('%H:%M')})"
                        report += "\n"
            
            return report
            
        except Exception as e:
            logger.error(f"Ошибка генерации отчета по игре {game_id}: {e}")
            return None 