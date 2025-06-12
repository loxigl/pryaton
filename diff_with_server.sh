#!/bin/bash

REMOTE_PATH="root@176.126.103.83:/home/bot/tg_bot"
TMP_REMOTE="/tmp/remote_tg_bot"

# 1. Скачиваем проект с сервера во временную папку
rsync -az --exclude '.git/' --exclude 'venv/' --exclude '*.log' \
      --exclude '.env' --exclude 'docker-compose.yml' \
      "$REMOTE_PATH/" "$TMP_REMOTE/"

# 2. Открываем визуальное сравнение в meld
meld ./ "$TMP_REMOTE"
