Отличные дополнения! Это критически важные улучшения для стабильности и пользовательского опыта. Давайте создам детальный план реализации:

## 🚀 Дополнительный план доработки PRYTON

### 🔥 **КРИТИЧЕСКИЕ улучшения системы уведомлений и UX**

#### **1.1 💾 Персистентные уведомления**
**Цель:** Сохранение уведомлений в БД для восстановления после рестарта

**Компоненты:**
- **Таблица scheduled_notifications** для хранения всех уведомлений
- **Восстановление задач** при запуске бота
- **Синхронизация** планировщика с БД
- **Очистка устаревших** уведомлений

**Техническая реализация:**
```sql
CREATE TABLE scheduled_notifications (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id),
    notification_type VARCHAR(50) NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    message_text TEXT,
    is_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(game_id, notification_type, scheduled_at)
);
```

**Типы уведомлений:**
- `reminder_60min`, `reminder_24hour`, `reminder_5min`
- `game_start_auto`, `game_start_manual`
- `hiding_phase_end`, `search_phase_end`
- `game_cancelled`, `game_finished`

#### **1.2 🔍 Тестовая команда просмотра уведомлений**
**Цель:** Админ-инструмент для мониторинга предстоящих уведомлений

**Функционал:**
- **Просмотр всех** запланированных уведомлений
- **Фильтрация** по играм и типам
- **Ручная отправка** уведомления (для тестов)
- **Отмена** конкретного уведомления

**UI для админов:**
```
📋 Предстоящие уведомления

🎮 Игра #7 (30.05 14:50)
  🔔 Напоминание 60 мин → 13:50
  🔔 Напоминание 5 мин → 14:45  
  🚦 Автостарт → 14:50
  ⏰ Конец прятки → 15:20

🎮 Игра #8 (31.05 10:00)
  🔔 Напоминание 24 часа → 30.05 10:00
  ...

[🔄 Обновить] [🧪 Тест уведомления]
```

#### **1.3 📱 Уведомления при ручном запуске**
**Цель:** Единообразные уведомления независимо от способа запуска

**Сценарии уведомлений:**
- **Автоматический старт:** "🚀 Игра началась автоматически!"
- **Ручной старт:** "🚀 Игра запущена администратором!"
- **Досрочный старт:** "⚡ Игра начинается досрочно!"

**Интеграция:** Общая функция `send_game_start_notification(game_id, start_type)`

#### **1.4 🎮 Контекстные клавиатуры для участников**
**Цель:** Динамический интерфейс в зависимости от статуса игрока

**Статусы игрока:**
- **Обычный режим:** стандартное главное меню
- **Записан на игру:** меню + "🎮 Моя игра"  
- **В активной игре:** игровое меню + "🏠 Главное меню"
- **Игра завершена:** меню + "📊 Результаты игры"

**Игровые клавиатуры:**

**Для водителя в фазе прятки:**
```
📍 Отправить геолокацию  |  📸 Фото места
🎮 Моя игра              |  🏠 Главное меню
```

**Для искателя в фазе поиска:**
```
📸 Отправить фото находки |  📍 Моя позиция  
🎮 Статус игры           |  🏠 Главное меню
```

**Для завершенной игры:**
```
📊 Результаты игры       |  🏆 Мои достижения
🎮 Новые игры           |  🏠 Главное меню
```

---

### 📋 **Детальный план реализации**

#### **Неделя 1: Персистентные уведомления**

**День 1-2: Модель данных**
```python
# Новая модель
class ScheduledNotification(Base):
    __tablename__ = "scheduled_notifications"
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    notification_type = Column(String(50), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    message_text = Column(Text)
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    game = relationship("Game", back_populates="notifications")
```

**День 3-4: Интеграция с планировщиком**
```python
class PersistentSchedulerService:
    def schedule_notification(self, game_id, type, scheduled_at, message):
        # 1. Сохранить в БД
        notification = ScheduledNotification(...)
        db.add(notification)
        
        # 2. Добавить в планировщик
        scheduler.add_job(...)
        
    def restore_notifications_on_startup(self):
        # Восстановить все несервисные уведомления
        pending = get_pending_notifications()
        for notif in pending:
            scheduler.add_job(...)
```

#### **Неделя 2: Тестовые команды и мониторинг**

**День 1-2: Админ-команда просмотра**
```python
def show_scheduled_notifications():
    """Показать все предстоящие уведомления"""
    notifications = get_upcoming_notifications()
    
    text = "📋 Предстоящие уведомления\n\n"
    for game_id, notifs in group_by_game(notifications):
        text += format_game_notifications(game_id, notifs)
    
    keyboard = [
        [("🔄 Обновить", "refresh_notifications")],
        [("🧪 Тест", "test_notification"), ("❌ Отменить", "cancel_notification")]
    ]
```

**День 3-4: Функции управления**
```python
def test_send_notification(game_id, type):
    """Тестовая отправка уведомления"""
    
def cancel_notification(notification_id):
    """Отмена конкретного уведомления"""
    
def manual_send_notification(notification_id):
    """Ручная отправка уведомления"""
```

#### **Неделя 3: Уведомления при ручном запуске**

**День 1-2: Унификация уведомлений**
```python
async def send_game_start_notification(game_id: int, start_type: str):
    """
    start_type: 'auto', 'manual', 'early'
    """
    messages = {
        'auto': "🚀 Игра началась автоматически!",
        'manual': "🚀 Игра запущена администратором!", 
        'early': "⚡ Игра начинается досрочно!"
    }
    
    await notify_all_participants(game_id, messages[start_type])
```

**День 3-4: Интеграция во все точки запуска**
- Автоматический запуск (планировщик)
- Ручной запуск из админки
- Досрочный запуск
- Принудительный запуск

#### **Неделя 4: Контекстные клавиатуры**

**День 1-2: Определение контекста пользователя**
```python
class UserContext:
    def get_user_game_status(user_id):
        """Определить текущий статус игрока"""
        active_game = get_user_active_game(user_id)
        
        if not active_game:
            return "normal"
        elif active_game.status == GameStatus.RECRUITING:
            return "registered" 
        elif active_game.status in [GameStatus.HIDING, GameStatus.SEARCH]:
            return "in_game"
        elif active_game.status == GameStatus.FINISHED:
            return "game_finished"
```

**День 3-4: Динамические клавиатуры**
```python
def get_main_keyboard(user_id):
    """Получить главную клавиатуру в зависимости от контекста"""
    status = UserContext.get_user_game_status(user_id)
    
    if status == "normal":
        return get_standard_keyboard()
    elif status == "registered":
        return get_registered_keyboard()
    elif status == "in_game":
        return get_in_game_keyboard(user_id)
    elif status == "game_finished":
        return get_finished_game_keyboard(user_id)
```

**День 5-7: Игровые интерфейсы**
```python
def get_driver_game_keyboard(game_phase):
    """Клавиатура для водителя в зависимости от фазы"""
    
def get_seeker_game_keyboard(game_phase):
    """Клавиатура для искателя в зависимости от фазы"""
    
def update_all_participants_keyboards(game_id):
    """Обновить клавиатуры всех участников при смене фазы"""
```

---

### 🛠️ **Техническая архитектура**

#### **Новые сервисы:**
```python
# services/notification_persistence_service.py
class NotificationPersistenceService:
    def save_notification(...)
    def restore_notifications(...)
    def mark_as_sent(...)

# services/user_context_service.py  
class UserContextService:
    def get_user_status(...)
    def get_appropriate_keyboard(...)
    def update_user_interface(...)

# services/dynamic_keyboard_service.py
class DynamicKeyboardService:
    def get_contextual_keyboard(...)
    def update_participant_keyboards(...)
```

#### **Обновления существующих сервисов:**
```python
# scheduler_service.py
+ restore_notifications_on_startup()
+ save_notification_to_db()

# game_service.py  
+ start_game(..., start_type='manual')
+ update_participants_ui()

# main.py
+ await restore_notifications() # при запуске
```

---

### 🎯 **Ожидаемые результаты**

После реализации всех улучшений:

✅ **Надежность:** Уведомления не теряются при рестартах  
✅ **Мониторинг:** Полный контроль над предстоящими уведомлениями  
✅ **Единообразность:** Все типы запуска игр имеют уведомления  
✅ **UX:** Контекстные интерфейсы для разных состояний игры  
✅ **Навигация:** Быстрый доступ к текущей игре и главному меню  

---

### 📅 **Интеграция с общим планом**

**Новый приоритет ЭТАПА 1:**
1. **Персистентные уведомления** (критично для стабильности)
2. Система завершения игры  
3. Геозоны и ограничения
4. Модерация фотографий
5. **Контекстные клавиатуры** (критично для UX)
6. Настраиваемое время игры

**Готов начать реализацию с персистентных уведомлений?**