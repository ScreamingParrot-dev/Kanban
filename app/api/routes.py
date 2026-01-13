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
from typing import List

from ..db.session import get_db
from ..models.database_and_models import User, Board, Task, Column
from ..schemas.schemas_and_auth import (
    UserCreate, UserRead, AuthHandler, 
    TaskCreate, TaskUpdate, TaskRead, BoardRead, MemberInvite,
    ColumnCreate, ColumnUpdate, ColumnRead
)
from ..services.kanban import KanbanService

router = APIRouter()

# --- AUTH ROUTES ---
@router.post("/register", response_model=UserRead)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == user_data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pw = AuthHandler.get_password_hash(user_data.password)
    new_user = User(username=user_data.username, email=user_data.email, hashed_password=hashed_pw)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    await KanbanService.create_board(db, f"Доска {new_user.username}", new_user.id)
    return new_user

@router.post("/login", response_model=UserRead)
async def login(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not AuthHandler.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    return user

# --- BOARD ROUTES ---
@router.get("/boards", response_model=List[BoardRead])
async def get_boards(user_id: int, db: AsyncSession = Depends(get_db)):
    return await KanbanService.get_user_boards(db, user_id)

@router.post("/boards/{board_id}/invite")
async def invite_to_board(board_id: int, invite: MemberInvite, db: AsyncSession = Depends(get_db)):
    success, message = await KanbanService.invite_member(db, board_id, invite.email)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"detail": "User invited successfully"}

# --- COLUMN ROUTES (NEW) ---
@router.post("/boards/{board_id}/columns", response_model=ColumnRead)
async def create_column(board_id: int, col_data: ColumnCreate, user_id: int, db: AsyncSession = Depends(get_db)):
    # Проверка прав: только владелец может добавлять колонки
    board_res = await db.execute(select(Board).where(Board.id == board_id))
    board = board_res.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if board.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only owner can manage columns")
        
    return await KanbanService.create_column(db, board_id, col_data.title, col_data.order)

@router.put("/columns/{column_id}", response_model=ColumnRead)
async def update_column(column_id: int, col_data: ColumnUpdate, user_id: int, db: AsyncSession = Depends(get_db)):
    # Находим колонку и её доску для проверки прав
    col_res = await db.execute(select(Column).where(Column.id == column_id))
    col = col_res.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")
        
    board_res = await db.execute(select(Board).where(Board.id == col.board_id))
    board = board_res.scalar_one_or_none()
    if board.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only owner can manage columns")

    return await KanbanService.update_column(db, column_id, col_data.title)

@router.delete("/columns/{column_id}")
async def delete_column(column_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    col_res = await db.execute(select(Column).where(Column.id == column_id))
    col = col_res.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")
        
    board_res = await db.execute(select(Board).where(Board.id == col.board_id))
    board = board_res.scalar_one_or_none()
    if board.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only owner can manage columns")
        
    await KanbanService.delete_column(db, column_id)
    return {"detail": "Column deleted"}

# --- TASK ROUTES ---
@router.post("/tasks", response_model=TaskRead)
async def create_task(task: TaskCreate, db: AsyncSession = Depends(get_db)):
    return await KanbanService.create_task(db, task)

@router.put("/tasks/{task_id}", response_model=TaskRead)
async def update_task(task_id: int, task_data: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await KanbanService.update_task(db, task_id, task_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    success = await KanbanService.delete_task(db, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"detail": "Task deleted"}

@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task_column(task_id: int, column_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.column_id = column_id
    await db.commit()
    await db.refresh(task)
    return task