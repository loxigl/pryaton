FROM python:3.10-slim

# Установка рабочей директории
WORKDIR /app

# Установка необходимых системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Проверка доступности базы данных
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "from sqlalchemy import create_engine; import os; engine = create_engine(os.getenv('DATABASE_URL')); engine.connect()"

# Запуск бота
CMD ["./run.sh"]