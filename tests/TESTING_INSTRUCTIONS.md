# 🧪 Инструкция по запуску тестов PRYTON v2

## 🚀 Быстрый запуск

### Запуск всех рабочих тестов:
```bash
# В Docker контейнере
docker compose exec bot python -m pytest tests/test_full_game_process.py tests/test_simplified_completion.py tests/test_scheduler_notifications.py -v

# Локально (если установлен pytest)
python -m pytest tests/test_full_game_process.py tests/test_simplified_completion.py tests/test_scheduler_notifications.py -v
```

### Запуск отдельных наборов:

#### 1. Полный игровой процесс (11 тестов):
```bash
docker compose exec bot python -m pytest tests/test_full_game_process.py -v -s
```

#### 2. Завершение игр и уведомления (6 тестов):
```bash
docker compose exec bot python -m pytest tests/test_simplified_completion.py -v -s
```

#### 3. Планировщик и автоматизация (14 тестов):
```bash
docker compose exec bot python -m pytest tests/test_scheduler_notifications.py -v -s
```

---

## 📋 Структура тестов

```
tests/
├── test_full_game_process.py      # Основной игровой процесс
├── test_simplified_completion.py  # Завершение игр (упрощённые)
├── test_scheduler_notifications.py # Планировщик и уведомления
├── test_game_completion_flow.py   # Завершение игр (проблемные)
├── run_all_tests.py              # Скрипт запуска всех тестов
├── requirements-test.txt          # Зависимости для тестов
└── README.md                     # Документация тестов
```

---

## ⚙️ Параметры запуска

### Полезные флаги pytest:
```bash
-v          # Подробный вывод
-s          # Показать print() в тестах
--tb=short  # Краткие трейсбеки ошибок
--tb=long   # Подробные трейсбеки
-x          # Остановиться на первой ошибке
-k pattern  # Запустить тесты по паттерну имени
```

### Примеры:
```bash
# Запуск с подробным выводом и остановкой на ошибке
docker compose exec bot python -m pytest tests/ -v -x

# Запуск только тестов с "notification" в имени
docker compose exec bot python -m pytest tests/ -k notification -v

# Запуск с покрытием кода (если установлен pytest-cov)
docker compose exec bot python -m pytest tests/ --cov=src --cov-report=html
```

---

## 🐛 Устранение проблем

### Если тесты не запускаются:
1. Убедитесь, что Docker контейнер запущен:
   ```bash
   docker compose up -d
   ```

2. Установите зависимости в контейнере:
   ```bash
   docker compose exec bot pip install pytest pytest-asyncio
   ```

3. Проверьте, что вы находитесь в правильной директории:
   ```bash
   docker compose exec bot pwd  # Должно показать /app
   ```

### Если есть ошибки импорта:
```bash
# Убедитесь, что PYTHONPATH настроен правильно
docker compose exec bot python -c "import sys; print('\n'.join(sys.path))"
```

---

## 📊 Ожидаемые результаты

### ✅ Успешный запуск должен показать:
```
======================== 31 passed, 3 warnings in 0.73s ========================
```

### 📋 Покрытие тестами:
- **test_full_game_process.py**: 11 тестов - полный цикл игры
- **test_simplified_completion.py**: 6 тестов - завершение игр  
- **test_scheduler_notifications.py**: 14 тестов - планировщик

**Всего: 31 тест** покрывает основную функциональность системы.

---

## 🔧 Для разработчиков

### Добавление новых тестов:
1. Создайте новый файл `test_*.py` в директории `tests/`
2. Используйте существующие fixture и паттерны мокирования
3. Следуйте структуре существующих тестов
4. Добавьте описательные docstring и print() для отладки

### Мокирование:
Все тесты используют Mock-объекты для изоляции от реальной базы данных и Telegram API. Основные паттерны:
- `Mock()` для обычных объектов
- `AsyncMock()` для асинхронных вызовов
- `patch.object()` для замены методов
- `patch()` для замены функций/модулей

### Fixture:
Используйте готовые fixture для создания тестовых объектов:
- `mock_update`, `mock_context` - для Telegram
- `test_user`, `admin_user` - для пользователей  
- `test_game`, `active_game` - для игр 