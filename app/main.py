"""
app.Main представляет собой точку входа в приложение,содержит инициализацию объекта FastAPI,
настройку жизненного цикла приложения для автоматического создания таблиц в базе данных
при старте, монтирование папки со статическими файлами (static) и подключение системы шаблонов Jinja2.
Собирает все части проекта воедино. Он определяет корневой маршрут для отображения главной страницы и
подключает все API-роутеры, чтобы выстроить порядок обработки запросов.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
import os
from contextlib import asynccontextmanager
from app.api.routes import router as kanban_router
from app.models.database_and_models import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Kanban Prototype", lifespan=lifespan)

# Создаем директории для загрузки файлов
os.makedirs("app/static/media", exist_ok=True)
os.makedirs("app/static/uploads", exist_ok=True)
os.makedirs("app/templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

app.include_router(kanban_router, prefix="/api/v1")