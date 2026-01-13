"""
Данный файл принудительно создаёт базу данных для корректной
работы тестов в GitHub Actions, а также содержит два теста,
один из которых пытается создать нового пользователя и
ожидает успешный ответ сервера, а второй пытается получить
доступ к несуществующей доске за неавторизованного пользователя,
ожидается, что вернётся пустой json список.
"""


import pytest
import pytest_asyncio
from httpx import AsyncClient
from app.main import app
from app.models.database_and_models import Base, engine

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database():
    """
    Автоматически создает таблицы перед каждым тестом 
    и удаляет их после завершения.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_register_user():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/v1/register", json={
            "username": "testuser_new",
            "email": "test_new@example.com",
            "password": "password123"
        })
    assert response.status_code == 200
    assert response.json()["username"] == "testuser_new"

@pytest.mark.asyncio
async def test_get_boards_unauthorized():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/boards?user_id=999")
    assert response.status_code == 200
    assert response.json() == []