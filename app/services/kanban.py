from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from ..models.database_and_models import Board, Column, Task, TaskPriority, User, BoardMember, BoardRole, TaskAttachment

class KanbanService:
    @staticmethod
    async def get_user_boards(db: AsyncSession, user_id: int) -> List[Board]:
        result = await db.execute(
            select(Board).join(BoardMember).where(BoardMember.user_id == user_id)
            .options(
                selectinload(Board.columns).selectinload(Column.tasks).selectinload(Task.assignee),
                selectinload(Board.columns).selectinload(Column.tasks).selectinload(Task.attachments),
                selectinload(Board.member_associations).selectinload(BoardMember.user)
            )
        )
        return result.scalars().unique().all()

    @staticmethod
    async def create_board(db: AsyncSession, title: str, user_id: int):
        new_board = Board(title=title)
        db.add(new_board)
        await db.flush()

        owner_assoc = BoardMember(user_id=user_id, board_id=new_board.id, role=BoardRole.OWNER)
        db.add(owner_assoc)

        default_columns = ["В плане", "В работе", "Готово"]
        for index, col_title in enumerate(default_columns):
            db.add(Column(title=col_title, order=index, board_id=new_board.id))
        
        await db.commit()
        await db.refresh(new_board)
        return new_board

    @staticmethod
    async def update_board(db: AsyncSession, board_id: int, title: str):
        result = await db.execute(select(Board).where(Board.id == board_id))
        board = result.scalar_one_or_none()
        if board:
            board.title = title
            await db.commit()
        return board

    @staticmethod
    async def delete_board(db: AsyncSession, board_id: int):
        result = await db.execute(select(Board).where(Board.id == board_id))
        board = result.scalar_one_or_none()
        if board:
            await db.delete(board)
            await db.commit()
            return True
        return False

    @staticmethod
    async def invite_member(db: AsyncSession, board_id: int, email: str, role_str: str):
        user_res = await db.execute(select(User).where(User.email == email))
        user = user_res.scalar_one_or_none()
        if not user: return None, "Пользователь не найден"

        member_res = await db.execute(select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == user.id))
        if member_res.scalar_one_or_none(): return None, "Пользователь уже в доске"

        try: role_enum = BoardRole[role_str.upper()]
        except KeyError: role_enum = BoardRole.MEMBER

        db.add(BoardMember(user_id=user.id, board_id=board_id, role=role_enum))
        await db.commit()
        return True, "Успешно"

    @staticmethod
    async def update_member_role(db: AsyncSession, board_id: int, user_id: int, role_str: str):
        result = await db.execute(select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == user_id))
        member = result.scalar_one_or_none()
        if member:
            try: member.role = BoardRole[role_str.upper()]
            except KeyError: pass
            await db.commit()
        return member

    @staticmethod
    async def remove_member(db: AsyncSession, board_id: int, user_id: int):
        result = await db.execute(select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == user_id))
        member = result.scalar_one_or_none()
        if member:
            await db.delete(member)
            await db.commit()
            return True
        return False

    @staticmethod
    async def update_user_profile(db: AsyncSession, user_id: int, description: str = None, avatar_url: str = None):
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            if description is not None: user.description = description
            if avatar_url is not None: user.avatar_url = avatar_url
            await db.commit()
            await db.refresh(user)
        return user

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
        if col:
            col.title = title
            await db.commit()
            await db.refresh(col)
        return col

    @staticmethod
    async def delete_column(db: AsyncSession, column_id: int):
        result = await db.execute(select(Column).where(Column.id == column_id))
        col = result.scalar_one_or_none()
        if col:
            await db.delete(col)
            await db.commit()
            return True
        return False

    @staticmethod
    async def create_task(db: AsyncSession, task_data):
        try: priority_enum = TaskPriority[task_data.priority.upper()]
        except KeyError: priority_enum = TaskPriority.MEDIUM

        new_task = Task(
            title=task_data.title, description=task_data.description,
            column_id=task_data.column_id, priority=priority_enum, assignee_id=task_data.assignee_id
        )
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
        return new_task

    @staticmethod
    async def update_task(db: AsyncSession, task_id: int, task_data):
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            if task_data.title: task.title = task_data.title
            if task_data.description is not None: task.description = task_data.description
            if task_data.priority:
                try: task.priority = TaskPriority[task_data.priority.upper()]
                except KeyError: pass 
            if task_data.assignee_id is not None:
                task.assignee_id = task_data.assignee_id if task_data.assignee_id > 0 else None
            await db.commit()
            await db.refresh(task)
        return task

    @staticmethod
    async def delete_task(db: AsyncSession, task_id: int):
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            await db.delete(task)
            await db.commit()
            return True
        return False

    @staticmethod
    async def add_task_attachment(db: AsyncSession, task_id: int, file_name: str, file_url: str):
        attachment = TaskAttachment(task_id=task_id, file_name=file_name, file_url=file_url)
        db.add(attachment)
        await db.commit()
        await db.refresh(attachment)
        return attachment