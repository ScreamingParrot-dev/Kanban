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

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# --- ENUMS ---
class TaskPriority(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class BoardRole(enum.Enum):
    OWNER = "OWNER"       # Полные права, удаление доски
    ADMIN = "ADMIN"       # Редактирование колонок, приглашение людей
    MEMBER = "MEMBER"     # Движение и создание задач
    VIEWER = "VIEWER"     # Только чтение

# --- ASSOCIATION OBJECT (Смежная таблица с ролями) ---
class BoardMember(Base):
    __tablename__ = "board_members"
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[BoardRole] = mapped_column(SqlEnum(BoardRole, native_enum=False), default=BoardRole.MEMBER)
    
    # Связи для ассоциации
    user: Mapped["User"] = relationship(back_populates="board_associations")
    board: Mapped["Board"] = relationship(back_populates="member_associations")

# --- MODELS ---
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    
    # Связь с досками через объект-ассоциацию
    board_associations: Mapped[list["BoardMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    
    # Задачи, назначенные на пользователя
    assigned_tasks: Mapped[list["Task"]] = relationship(back_populates="assignee")

class Board(Base):
    __tablename__ = "boards"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    background_url: Mapped[str | None] = mapped_column(String(255)) # Задел на кастомный фон
    
    # Владельца больше не храним отдельным полем, он будет в board_members с ролью OWNER
    
    # Связь с пользователями через объект-ассоциацию
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
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL")) # Исполнитель
    
    column: Mapped["Column"] = relationship(back_populates="tasks")
    assignee: Mapped["User"] = relationship(back_populates="assigned_tasks")