from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from ..models.database_and_models import Board, Column, Task, TaskPriority, User, BoardMember, BoardRole

class KanbanService:
    @staticmethod
    async def get_user_boards(db: AsyncSession, user_id: int) -> List[Board]:
        # Получаем доски, где пользователь является участником (любая роль)
        result = await db.execute(
            select(Board)
            .join(BoardMember)
            .where(BoardMember.user_id == user_id)
            .options(
                selectinload(Board.columns).selectinload(Column.tasks).selectinload(Task.assignee),
                selectinload(Board.member_associations).selectinload(BoardMember.user)
            )
        )
        return result.scalars().unique().all()

    @staticmethod
    async def create_board(db: AsyncSession, title: str, user_id: int):
        new_board = Board(title=title)
        db.add(new_board)
        await db.flush() # Получаем ID доски

        # Создаем связь с ролью ВЛАДЕЛЕЦ
        owner_assoc = BoardMember(user_id=user_id, board_id=new_board.id, role=BoardRole.OWNER)
        db.add(owner_assoc)

        default_columns = ["В плане", "В работе", "Готово"]
        for index, col_title in enumerate(default_columns):
            new_col = Column(title=col_title, order=index, board_id=new_board.id)
            db.add(new_col)
        
        await db.commit()
        await db.refresh(new_board)
        return new_board

    @staticmethod
    async def invite_member(db: AsyncSession, board_id: int, email: str, role_str: str):
        # Ищем пользователя по email
        user_res = await db.execute(select(User).where(User.email == email))
        user = user_res.scalar_one_or_none()
        if not user:
            return None, "User not found"

        # Проверяем, нет ли его уже в доске
        member_res = await db.execute(
            select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == user.id)
        )
        existing_member = member_res.scalar_one_or_none()
        if existing_member:
            return None, "User is already in the board"

        try:
            role_enum = BoardRole[role_str.upper()]
        except KeyError:
            role_enum = BoardRole.MEMBER

        new_member = BoardMember(user_id=user.id, board_id=board_id, role=role_enum)
        db.add(new_member)
        await db.commit()
        
        return True, "Success"

    # --- COLUMN MANAGEMENT (Менеджмент колонок) ---
    @staticmethod
    async def create_column(db: AsyncSession, board_id: int, title: str, order: int):
        new_col = Column(title=title, order=order, board_id=board_id)
        db.add(new_col)
        await db.commit()
        await db.refresh(new_col)
        return new_col

    @staticmethod
    async def update_column(db: AsyncSession, column_id: int, title: str):
        result = await db.execute(select(Column).where(Column.id == column_id))
        col = result.scalar_one_or_none()
        if not col:
            return None
        col.title = title
        await db.commit()
        await db.refresh(col)
        return col

    @staticmethod
    async def delete_column(db: AsyncSession, column_id: int):
        result = await db.execute(select(Column).where(Column.id == column_id))
        col = result.scalar_one_or_none()
        if not col:
            return False
        await db.delete(col)
        await db.commit()
        return True

    # --- TASK MANAGEMENT (Менеджмент задач) ---
    @staticmethod
    async def create_task(db: AsyncSession, task_data):
        try:
            priority_enum = TaskPriority[task_data.priority.upper()]
        except KeyError:
            priority_enum = TaskPriority.MEDIUM

        new_task = Task(
            title=task_data.title,
            description=task_data.description,
            column_id=task_data.column_id,
            priority=priority_enum
        )
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
        return new_task

    @staticmethod
    async def update_task(db: AsyncSession, task_id: int, task_data):
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return None

        if task_data.title:
            task.title = task_data.title
        if task_data.description is not None:
            task.description = task_data.description
        if task_data.priority:
            try:
                task.priority = TaskPriority[task_data.priority.upper()]
            except KeyError:
                pass 
        
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def delete_task(db: AsyncSession, task_id: int):
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return False
        
        await db.delete(task)
        await db.commit()
        return True