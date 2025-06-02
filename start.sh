#!/bin/bash

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "Файл .env не найден. Создаю пример файла..."
    cat > .env << EOF
# Токен Telegram бота (получить у @BotFather)
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Настройки базы данных (для Docker)
DATABASE_URL=postgresql://user:password@db:5432/pryton_bot

# Переменные для PostgreSQL контейнера
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=pryton_bot

# Настройки приложения
DEBUG=True
ADMIN_USER_IDS=123456789,987654321

# Настройки геолокации
# Радиус игровой зоны в метрах
GAME_ZONE_RADIUS=1000

# Настройки таймеров
# Время на прятки (в минутах)
HIDING_TIME=30
# За сколько минут отправлять напоминания об игре
REMINDER_BEFORE_GAME=60,24,5
EOF
    echo "Создан файл .env. Пожалуйста, отредактируйте его и замените 'your_telegram_bot_token_here' на реальный токен бота."
    echo "После редактирования запустите скрипт повторно."
    exit 1
fi

# Проверка токена
TOKEN=$(grep TELEGRAM_TOKEN .env | cut -d= -f2)
if [[ "$TOKEN" == "your_telegram_bot_token_here" ]]; then
    echo "Пожалуйста, замените 'your_telegram_bot_token_here' в файле .env на реальный токен бота."
    exit 1
fi

# Создание директории для логов, если её нет
mkdir -p logs

# Запуск контейнеров
echo "Запуск PRYTON бота..."
docker-compose down
docker-compose up -d --build

echo "Проверка статуса контейнеров..."
sleep 5
docker-compose ps

echo "Для просмотра логов выполните: docker-compose logs -f"
echo "Для остановки бота выполните: ./stop.sh" 