import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_register_user():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/v1/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "strongpassword123"
        })
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"

@pytest.mark.asyncio
async def test_get_boards_unauthorized():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Пытаемся получить доски без корректного user_id
        response = await ac.get("/api/v1/boards?user_id=999")
    assert response.status_code == 200
    assert response.json() == [] # Вернет пустой список, так как пользователя нет