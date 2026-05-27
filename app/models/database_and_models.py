"""
Конфигурация подключения к PostgreSQL, описание констант enum для ролей и приоритетов,
объект-ассоциация для многопользовательского доступа с ролями,
а также модели для создания таблиц в базе данных.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Integer, Text, Enum as SqlEnum
import enum
import os

# --- DATABASE CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:leon1511@localhost:5438/postgres")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# --- ENUMS ---
class TaskPriority(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class BoardRole(enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"

# --- ASSOCIATION OBJECT ---
class BoardMember(Base):
    __tablename__ = "board_members"
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[BoardRole] = mapped_column(SqlEnum(BoardRole, native_enum=False), default=BoardRole.MEMBER)
    
    user: Mapped["User"] = relationship(back_populates="board_associations")
    board: Mapped["Board"] = relationship(back_populates="member_associations")

# --- MODELS ---
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(255))
    
    board_associations: Mapped[list["BoardMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    assigned_tasks: Mapped[list["Task"]] = relationship(back_populates="assignee")

class Board(Base):
    __tablename__ = "boards"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    background_url: Mapped[str | None] = mapped_column(String(255))
    
    member_associations: Mapped[list["BoardMember"]] = relationship(
        back_populates="board", cascade="all, delete-orphan"
    )
    columns: Mapped[list["Column"]] = relationship(back_populates="board", cascade="all, delete-orphan")

class Column(Base):
    __tablename__ = "columns"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50))
    order: Mapped[int] = mapped_column(Integer, default=0)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"))
    
    board: Mapped["Board"] = relationship(back_populates="columns")
    tasks: Mapped[list["Task"]] = relationship(back_populates="column", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[TaskPriority] = mapped_column(
        SqlEnum(TaskPriority, native_enum=False), 
        default=TaskPriority.MEDIUM
    )
    column_id: Mapped[int] = mapped_column(ForeignKey("columns.id", ondelete="CASCADE"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    
    column: Mapped["Column"] = relationship(back_populates="tasks")
    assignee: Mapped["User"] = relationship(back_populates="assigned_tasks")
    attachments: Mapped[list["TaskAttachment"]] = relationship(back_populates="task", cascade="all, delete-orphan")

class TaskAttachment(Base):
    __tablename__ = "task_attachments"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_url: Mapped[str] = mapped_column(String(500))
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    
    task: Mapped["Task"] = relationship(back_populates="attachments")