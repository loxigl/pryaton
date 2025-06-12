#!/bin/bash

REMOTE="root@176.126.103.83"
REMOTE_DIR="/home/bot/tg_bot"
EXCLUDES=(
  --exclude '.git/'
  --exclude 'venv/'
  --exclude '*.log*'
  --exclude '.env'
  --exclude 'docker-compose.yml'
)

# Получаем список изменённых файлов
CHANGED_FILES=$(rsync -avnc --delete "${EXCLUDES[@]}" ./ "$REMOTE:$REMOTE_DIR/" \
  | grep -vE '^\.\/$|^sending|^sent|^total size|^created|^deleting' \
  | sed 's/^\.\/\(.*\)/\1/' \
  | fzf -m --prompt="Выбери файлы для заливки: ")

# Если ничего не выбрано — выходим
if [[ -z "$CHANGED_FILES" ]]; then
  echo "Ничего не выбрано — отмена."
  exit 0
fi

echo "Выбранные файлы:"
echo "$CHANGED_FILES"
echo

# Создаём временную директорию для сравнения
TMP_DIR=$(mktemp -d)

# Пробегаемся по каждому выбранному файлу
while IFS= read -r file; do
  LOCAL_FILE="$file"
  REMOTE_FILE="$TMP_DIR/$file"

  # Создаём подкаталоги, если нужно
  mkdir -p "$(dirname "$REMOTE_FILE")"

  # Скачиваем файл с удалённого сервера
  rsync -az "$REMOTE:$REMOTE_DIR/$file" "$REMOTE_FILE" 2>/dev/null

  if [[ -f "$REMOTE_FILE" ]]; then
    echo "Diff для $file:"
    GIT_PAGER=cat git diff --no-index "$REMOTE_FILE" "$LOCAL_FILE" || true
  else
    echo "Файл $file отсутствует на сервере (новый файл?)"
  fi

  echo
  read -p "Отправить файл '$file'? (y/N) " confirm < /dev/tty
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "Заливаем $file..."
    rsync -avz "$LOCAL_FILE" "$REMOTE:$REMOTE_DIR/$file"
  else
    echo "Пропускаем $file."
  fi
  echo

done <<< "$CHANGED_FILES"

# Удаляем временные файлы
rm -rf "$TMP_DIR"
