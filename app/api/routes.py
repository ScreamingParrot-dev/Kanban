"""
api.routes отвечает за определение путей (endpoints), по которым фронтенд коннектится с бэкендом.
Содержит определения HTTP-методов (GET, POST, PUT, DELETE) для конкретных URL, таких как /register, /boards или /tasks. 
Он использует зависимости (Depends) для получения доступа к сессии базы данных.
Служит диспетчером запросов. Он принимает данные от пользователя (через Pydantic-схемы), 
вызывает соответствующие методы из сервисного слоя и возвращает ответ клиенту. 
Здесь сосредоточена логика общения внешнего мира с приложением.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
import shutil
import uuid
import os

from ..db.session import get_db
from ..models.database_and_models import User, Board, Task, Column, BoardMember, BoardRole
from ..schemas.schemas_and_auth import (
    UserCreate, UserLogin, UserRead, AuthHandler, TaskCreate, TaskUpdate, 
    TaskRead, BoardRead, MemberInvite, ColumnCreate, ColumnUpdate, ColumnRead, 
    BoardCreate, BoardUpdate, UserProfileUpdate, MemberRoleUpdate, TaskAttachmentRead
)
from ..services.kanban import KanbanService

router = APIRouter()

# --- Вспомогательные функции ---
async def check_board_permission(db: AsyncSession, board_id: int, user_id: int, allowed_roles: list[BoardRole]):
    stmt = select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == user_id)
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()
    if not member or member.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return member

async def get_board_id_by_column(db: AsyncSession, column_id: int) -> int:
    result = await db.execute(select(Column).where(Column.id == column_id))
    col = result.scalar_one_or_none()
    if not col: raise HTTPException(status_code=404, detail="Колонка не найдена")
    return col.board_id

async def get_board_id_by_task(db: AsyncSession, task_id: int) -> int:
    result = await db.execute(select(Task).options(selectinload(Task.column)).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task: raise HTTPException(status_code=404, detail="Задача не найдена")
    return task.column.board_id

# --- USER PROFILE ROUTES ---
@router.put("/users/me", response_model=UserRead)
async def update_profile(profile_data: UserProfileUpdate, user_id: int, db: AsyncSession = Depends(get_db)):
    updated_user = await KanbanService.update_user_profile(db, user_id, description=profile_data.description)
    if not updated_user: raise HTTPException(status_code=404, detail="Пользователь не найден")
    return updated_user

@router.post("/users/me/avatar", response_model=UserRead)
async def upload_avatar(user_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    ext = file.filename.split(".")[-1]
    filename = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
    path = f"app/static/uploads/{filename}"
    with open(path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    
    updated_user = await KanbanService.update_user_profile(db, user_id, avatar_url=f"/static/uploads/{filename}")
    return updated_user

# --- AUTH ROUTES ---
@router.post("/register", response_model=UserRead)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == user_data.username))
    if existing.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Имя занято")
    
    hashed_pw = AuthHandler.get_password_hash(user_data.password)
    new_user = User(username=user_data.username, email=user_data.email, hashed_password=hashed_pw)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    await KanbanService.create_board(db, f"Доска {new_user.username}", new_user.id)
    return new_user

@router.post("/login", response_model=UserRead)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not AuthHandler.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверные данные входа")
    return user

# --- BOARD ROUTES ---
@router.get("/boards", response_model=List[BoardRead])
async def get_boards(user_id: int, db: AsyncSession = Depends(get_db)):
    return await KanbanService.get_user_boards(db, user_id)

@router.post("/boards", response_model=BoardRead)
async def create_new_board(board_data: BoardCreate, user_id: int, db: AsyncSession = Depends(get_db)):
    new_board = await KanbanService.create_board(db, board_data.title, user_id)
    boards = await KanbanService.get_user_boards(db, user_id)
    return next((b for b in boards if b.id == new_board.id), new_board)

@router.put("/boards/{board_id}", response_model=BoardRead)
async def update_board_info(board_id: int, board_data: BoardUpdate, user_id: int, db: AsyncSession = Depends(get_db)):
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    await KanbanService.update_board(db, board_id, board_data.title)
    boards = await KanbanService.get_user_boards(db, user_id)
    return next((b for b in boards if b.id == board_id), None)

@router.delete("/boards/{board_id}")
async def delete_board(board_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER])
    success = await KanbanService.delete_board(db, board_id)
    if not success: raise HTTPException(status_code=404, detail="Доска не найдена")
    return {"detail": "Доска удалена"}

# --- MEMBER ROUTES ---
@router.post("/boards/{board_id}/invite")
async def invite_to_board(board_id: int, invite: MemberInvite, user_id: int, db: AsyncSession = Depends(get_db)):
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    success, message = await KanbanService.invite_member(db, board_id, invite.email, invite.role)
    if not success: raise HTTPException(status_code=400, detail=message)
    return {"detail": "Приглашен"}

@router.put("/boards/{board_id}/members/{target_user_id}")
async def update_member(board_id: int, target_user_id: int, data: MemberRoleUpdate, user_id: int, db: AsyncSession = Depends(get_db)):
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    await KanbanService.update_member_role(db, board_id, target_user_id, data.role)
    return {"detail": "Роль обновлена"}

@router.delete("/boards/{board_id}/members/{target_user_id}")
async def kick_member(board_id: int, target_user_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    await KanbanService.remove_member(db, board_id, target_user_id)
    return {"detail": "Исключен"}

# --- COLUMN ROUTES ---
@router.post("/boards/{board_id}/columns", response_model=ColumnRead)
async def create_column(board_id: int, col_data: ColumnCreate, user_id: int, db: AsyncSession = Depends(get_db)):
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    return await KanbanService.create_column(db, board_id, col_data.title, col_data.order)

@router.put("/columns/{column_id}", response_model=ColumnRead)
async def update_column(column_id: int, col_data: ColumnUpdate, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_column(db, column_id)
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    return await KanbanService.update_column(db, column_id, col_data.title)

@router.delete("/columns/{column_id}")
async def delete_column(column_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_column(db, column_id)
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN])
    await KanbanService.delete_column(db, column_id)
    return {"detail": "Удалено"}

# --- TASK ROUTES ---
@router.post("/tasks", response_model=TaskRead)
async def create_task(task: TaskCreate, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_column(db, task.column_id)
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN, BoardRole.MEMBER])
    return await KanbanService.create_task(db, task)

@router.put("/tasks/{task_id}", response_model=TaskRead)
async def update_task(task_id: int, task_data: TaskUpdate, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_task(db, task_id)
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN, BoardRole.MEMBER])
    updated_task = await KanbanService.update_task(db, task_id, task_data)
    if not updated_task: raise HTTPException(status_code=404)
    return updated_task

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_task(db, task_id)
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN, BoardRole.MEMBER])
    await KanbanService.delete_task(db, task_id)
    return {"detail": "Удалено"}

@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task_column(task_id: int, column_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_task(db, task_id)
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN, BoardRole.MEMBER])
    if board_id != await get_board_id_by_column(db, column_id):
        raise HTTPException(status_code=400, detail="Нельзя переместить в чужую доску")
    
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    task.column_id = column_id
    await db.commit()
    return task

@router.post("/tasks/{task_id}/attachments", response_model=TaskAttachmentRead)
async def upload_task_file(task_id: int, user_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    board_id = await get_board_id_by_task(db, task_id)
    await check_board_permission(db, board_id, user_id, [BoardRole.OWNER, BoardRole.ADMIN, BoardRole.MEMBER])
    
    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = f"app/static/uploads/{filename}"
    with open(path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    
    return await KanbanService.add_task_attachment(db, task_id, file.filename, f"/static/uploads/{filename}")