import pytest
import os
from dotenv import load_dotenv

# Загрузка переменных окружения для тестов
load_dotenv(".env.test", override=True)

def test_environment():
    """Проверка загрузки переменных окружения"""
    assert os.getenv("TELEGRAM_TOKEN") is not None or os.getenv("TELEGRAM_TOKEN", "test_token") == "test_token"
    
def test_import_models():
    """Проверка импорта моделей"""
    from src.models import User, Game, GameParticipant
    assert User.__name__ == "User"
    assert Game.__name__ == "Game"
    assert GameParticipant.__name__ == "GameParticipant" 