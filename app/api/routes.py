"""
api.routes отвечает за определение путей (endpoints), по которым фронтенд коннектится с бэкендом.
Содержит определения HTTP-методов (GET, POST, PUT, DELETE) для конкретных URL, таких как /register, /boards или /tasks. 
Он использует зависимости (Depends) для получения доступа к сессии базы данных.
Служит диспетчером запросов. Он принимает данные от пользователя (через Pydantic-схемы), 
вызывает соответствующие методы из сервисного слоя и возвращает ответ клиенту. 
Здесь сосредоточена логика общения внешнего мира с приложением.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from ..db.session import get_db
from ..models.database_and_models import User, Board, Task, Column, BoardMember, BoardRole
from ..schemas.schemas_and_auth import (
    UserCreate, UserRead, AuthHandler, TaskCreate, TaskUpdate, 
    TaskRead, BoardRead, MemberInvite, ColumnCreate, ColumnUpdate, ColumnRead
)
from ..services.kanban import KanbanService

router = APIRouter()

# --- Вспомогательные функции проверки прав и поиска ---
async def check_board_permission(db: AsyncSession, board_id: int, user_id: int, allowed_roles: list[BoardRole]):
    """Проверяет, есть ли у пользователя нужная роль в указанной доске."""
    stmt = select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == user_id)
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()
    if not member or member.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Недостаточно прав для выполнения операции")
    return member

async def get_board_id_by_column(db: AsyncSession, column_id: int) -> int:
    """Определяет ID доски, к которой принадлежит колонка."""
    result = await db.execute(select(Column).where(Column.id == column_id))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Колонка не найдена")
    return col.board_id

async def get_board_id_by_task(db: AsyncSession, task_id: int) -> int:
    """Определяет ID доски, к которой принадлежит задача (через колонку)."""
    result = await db.execute(select(Task).options(selectinload(Task.column)).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task.column.board_id


# --- AUTH ROUTES (Аутентификация) ---
@router.post("/register", response_model=UserRead)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == user_data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
    
    hashed_pw = AuthHandler.get_password_hash(user_data.password)
    new_user = User(username=user_data.username, email=user_data.email, hashed_password=hashed_pw)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Автоматически создаем приветственную доску (пользователь становится OWNER)
    await KanbanService.create_board(db, f"Доска {new_user.username}", new_user.id)
    return new_user

@router.post("/login", response_model=UserRead)
async def login(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not AuthHandler.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверные учетные данные")
    
    return user


# --- BOARD ROUTES (Доски) ---
@router.get("/boards", response_model=List[BoardRead])
async def get_boards(user_id: int, db: AsyncSession = Depends(get_db)):
    # Получаем все доски, где пользователь является участником с любой ролью
    return await KanbanService.get_user_boards(db, user_id)

@router.post("/boards/{board_id}/invite")
async def invite_to_board(board_id: int, invite: MemberInvite, user_id: int, db: AsyncSession = Depends(get_db)):
    # Только Владелец и Админ могут приглашать людей
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    
    success, message = await KanbanService.invite_member(db, board_id, invite.email, invite.role)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"detail": "Пользователь успешно приглашен"}


# --- COLUMN ROUTES (Колонки) ---
@router.post("/boards/{board_id}/columns", response_model=ColumnRead)
async def create_column(board_id: int, col_data: ColumnCreate, user_id: int, db: AsyncSession = Depends(get_db)):
    # Только Владелец и Админ могут создавать колонки
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    return await KanbanService.create_column(db, board_id, col_data.title, col_data.order)

@router.put("/columns/{column_id}", response_model=ColumnRead)
async def update_column(column_id: int, col_data: ColumnUpdate, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_column(db, column_id)
    # Только Владелец и Админ могут переименовывать колонки
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    return await KanbanService.update_column(db, column_id, col_data.title)

@router.delete("/columns/{column_id}")
async def delete_column(column_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_column(db, column_id)
    # Только Владелец и Админ могут удалять колонки
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    
    await KanbanService.delete_column(db, column_id)
    return {"detail": "Колонка удалена"}


# --- TASK ROUTES (Задачи) ---
@router.post("/tasks", response_model=TaskRead)
async def create_task(task: TaskCreate, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_column(db, task.column_id)
    # Создавать задачи могут Владельцы, Админы и Участники (но не Наблюдатели)
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN, BoardRole.MEMBER])
    return await KanbanService.create_task(db, task)

@router.put("/tasks/{task_id}", response_model=TaskRead)
async def update_task(task_id: int, task_data: TaskUpdate, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_task(db, task_id)
    # Редактировать задачи могут Владельцы, Админы и Участники
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN, BoardRole.MEMBER])
    
    updated_task = await KanbanService.update_task(db, task_id, task_data)
    if not updated_task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return updated_task

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_task(db, task_id)
    # Удалять задачи могут Владельцы, Админы и Участники
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN, BoardRole.MEMBER])
    
    success = await KanbanService.delete_task(db, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"detail": "Задача удалена"}

@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task_column(task_id: int, column_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    # 1. Проверяем права на доску, к которой принадлежит задача сейчас
    board_id = await get_board_id_by_task(db, task_id)
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN, BoardRole.MEMBER])
    
    # 2. Защита от переноса задачи в чужую доску (проверяем, принадлежит ли новая колонка той же доске)
    new_board_id = await get_board_id_by_column(db, column_id)
    if board_id != new_board_id:
        raise HTTPException(status_code=400, detail="Невозможно переместить задачу в другую доску")
    
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    task.column_id = column_id
    await db.commit()
    await db.refresh(task)
    return task