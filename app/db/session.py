from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from ..models.database_and_models import async_session

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Функция-генератор (Dependency), которая создает новую сессию БД
    для каждого HTTP-запроса и гарантированно закрывает её после завершения.
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            # Закрытие сессии происходит автоматически благодаря контекстному менеджеру 'async with'
            await session.close()