#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Использование: $0 [команда]"
    echo "Доступные команды:"
    echo "  init       - Инициализация директории миграций"
    echo "  create     - Создание новой миграции (пустой)"
    echo "  revision   - Создание новой ревизии (автоматическое определение изменений)"
    echo "  upgrade    - Применение всех миграций"
    echo "  downgrade  - Откат последней миграции"
    echo "  history    - Показать историю миграций"
    echo "  current    - Показать текущую ревизию"
    echo "  heads      - Показать последние ревизии"
    echo "  help       - Показать эту справку"
    exit 1
fi

# Проверка, запущены ли контейнеры
if ! docker-compose ps | grep -q "bot"; then
    echo "Контейнеры не запущены. Сначала запустите приложение: ./start.sh"
    exit 1
fi

COMMAND=$1
shift

case $COMMAND in
    init)
        echo "Инициализация директории миграций..."
        docker-compose exec bot alembic init -t generic alembic
        ;;
    create)
        if [ $# -eq 0 ]; then
            echo "Необходимо указать имя миграции"
            echo "Использование: $0 create [имя_миграции]"
            exit 1
        fi
        echo "Создание пустой миграции '$1'..."
        docker-compose exec bot alembic revision -m "$1"
        ;;
    revision)
        if [ $# -eq 0 ]; then
            echo "Необходимо указать имя ревизии"
            echo "Использование: $0 revision [имя_ревизии]"
            exit 1
        fi
        echo "Создание автоматической ревизии '$1'..."
        docker-compose exec bot alembic revision --autogenerate -m "$1"
        ;;
    upgrade)
        if [ $# -eq 0 ]; then
            echo "Применение всех миграций..."
            docker-compose exec bot alembic upgrade head
        else
            echo "Применение $1 миграций..."
            docker-compose exec bot alembic upgrade $1
        fi
        ;;
    downgrade)
        if [ $# -eq 0 ]; then
            echo "Откат последней миграции..."
            docker-compose exec bot alembic downgrade -1
        else
            echo "Откат на $1 миграций назад..."
            docker-compose exec bot alembic downgrade $1
        fi
        ;;
    history)
        echo "История миграций:"
        docker-compose exec bot alembic history
        ;;
    current)
        echo "Текущая ревизия:"
        docker-compose exec bot alembic current
        ;;
    heads)
        echo "Последние ревизии:"
        docker-compose exec bot alembic heads
        ;;
    help)
        echo "Использование: $0 [команда]"
        echo "Доступные команды:"
        echo "  init       - Инициализация директории миграций"
        echo "  create     - Создание новой миграции (пустой)"
        echo "  revision   - Создание новой ревизии (автоматическое определение изменений)"
        echo "  upgrade    - Применение всех миграций"
        echo "  downgrade  - Откат последней миграции"
        echo "  history    - Показать историю миграций"
        echo "  current    - Показать текущую ревизию"
        echo "  heads      - Показать последние ревизии"
        echo "  help       - Показать эту справку"
        ;;
    *)
        echo "Неизвестная команда: $COMMAND"
        echo "Используйте '$0 help' для получения справки"
        exit 1
        ;;
esac

exit 0