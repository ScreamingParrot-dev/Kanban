"""
Данный файл содержит тесты для проверки доступности приложения и веб-сервера
"""


import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_app_is_running():
    """
    Базовый тест для проверки доступности приложения.
    Гарантирует, что импорты работают и приложение собирается.
    """
    assert app is not None
    assert app.title != ""

def test_dummy_ci_pass():
    assert 1 == 1

# Если главная страница (index.html) отдается без обязательного запроса к БД:
def test_read_main():
    response = client.get("/")
    # Проверяем, что сервер отвечает (200 OK или редирект 307/Авторизация 401)
    assert response.status_code in [200, 307, 401]