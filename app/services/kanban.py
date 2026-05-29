from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List
from ..models.database_and_models import Board, Column, Task, TaskPriority, User, BoardMember, BoardRole, TaskAttachment

class KanbanService:
    # --- ADMIN / SYSTEM ---
    @staticmethod
    async def get_system_stats(db: AsyncSession):
        users_count = await db.scalar(select(func.count(User.id)))
        boards_count = await db.scalar(select(func.count(Board.id)))
        # Надежная проверка: берем всё, что False или None
        tasks_count = await db.scalar(select(func.count(Task.id)).where((Task.is_deleted == False) | (Task.is_deleted.is_(None))))
        deleted_count = await db.scalar(select(func.count(Task.id)).where(Task.is_deleted == True))
        return {
            "total_users": users_count or 0, 
            "total_boards": boards_count or 0, 
            "total_tasks": tasks_count or 0,
            "total_deleted_tasks": deleted_count or 0
        }

    @staticmethod
    async def get_all_users(db: AsyncSession):
        result = await db.execute(select(User))
        return result.scalars().all()

    @staticmethod
    async def admin_delete_user(db: AsyncSession, user_id: int):
        user = await db.get(User, user_id)
        if user:
            await db.delete(user)
            await db.commit()
            return True
        return False

    @staticmethod
    async def update_user_password(db: AsyncSession, user_id: int, new_hashed_password: str):
        user = await db.get(User, user_id)
        if user:
            user.hashed_password = new_hashed_password
            await db.commit()
            return True
        return False

    # --- BOARDS & MEMBERS ---
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
        boards = result.scalars().unique().all()
        for board in boards:
            for col in board.columns:
                col.tasks = [t for t in col.tasks if not getattr(t, 'is_deleted', False)]
        return boards

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

    # --- COLUMN & TASK MANAGEMENT ---
    @staticmethod
    async def create_column(db: AsyncSession, board_id: int, title: str, order: int):
        new_col = Column(title=title, order=order, board_id=board_id)
        db.add(new_col)
        await db.commit()
        
        # Полная подгрузка связей во избежание MissingGreenlet Error
        result = await db.execute(
            select(Column).where(Column.id == new_col.id)
            .options(
                selectinload(Column.tasks).selectinload(Task.assignee),
                selectinload(Column.tasks).selectinload(Task.attachments)
            )
        )
        return result.scalar_one()

    @staticmethod
    async def update_column(db: AsyncSession, column_id: int, title: str):
        result = await db.execute(select(Column).where(Column.id == column_id))
        col = result.scalar_one_or_none()
        if col:
            col.title = title
            await db.commit()
            
            # Перезапрашиваем со всеми связями
            res2 = await db.execute(
                select(Column).where(Column.id == column_id)
                .options(
                    selectinload(Column.tasks).selectinload(Task.assignee),
                    selectinload(Column.tasks).selectinload(Task.attachments)
                )
            )
            return res2.scalar_one()
        return None

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
            title=task_data.title, 
            description=task_data.description,
            column_id=task_data.column_id, 
            priority=priority_enum, 
            assignee_id=task_data.assignee_id,
            is_deleted=False
        )
        db.add(new_task)
        await db.commit()
        
        result = await db.execute(
            select(Task).where(Task.id == new_task.id)
            .options(selectinload(Task.assignee), selectinload(Task.attachments))
        )
        return result.scalar_one()

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
            
            result_updated = await db.execute(
                select(Task).where(Task.id == task_id)
                .options(selectinload(Task.assignee), selectinload(Task.attachments))
            )
            return result_updated.scalar_one()
        return None

    @staticmethod
    async def delete_task(db: AsyncSession, task_id: int):
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            task.is_deleted = True
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