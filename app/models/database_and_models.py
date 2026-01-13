"""
Данный файл содержит конфигурацию подключения к БД, описание констант enum,
смежную таблицу многие ко многим для многопользовательского доступа к досками,
а также модели для создания таблиц в базе данных.
"""


from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Integer, Text, Enum as SqlEnum, Table, Column as SqlColumn
import enum

# --- DATABASE CONFIGURATION (Конфигурация БД) ---
DATABASE_URL = "sqlite+aiosqlite:///./kanban.db"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# --- ENUMS (Список констант enum для приоритетов) ---
class TaskPriority(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

# --- Таблица связей для многопользовательского доступа к доскам (многие-ко-многим) ---
board_members = Table(
    "board_members",
    Base.metadata,
    SqlColumn("user_id", ForeignKey("users.id"), primary_key=True),
    SqlColumn("board_id", ForeignKey("boards.id"), primary_key=True),
)

# --- MODELS (Модели таблиц) ---

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    
    # Личные доски (где пользователь — владелец)
    owned_boards: Mapped[list["Board"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    
    # Доски, к которым есть общий доступ
    shared_boards: Mapped[list["Board"]] = relationship(
        secondary=board_members, back_populates="members"
    )
    
    tasks: Mapped[list["Task"]] = relationship(back_populates="assignee")

class Board(Base):
    __tablename__ = "boards"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    owner: Mapped["User"] = relationship(back_populates="owned_boards")
    
    # Пользователи, имеющие доступ к доске
    members: Mapped[list["User"]] = relationship(
        secondary=board_members, back_populates="shared_boards"
    )
    
    columns: Mapped[list["Column"]] = relationship(back_populates="board", cascade="all, delete-orphan")

class Column(Base):
    __tablename__ = "columns"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50))
    order: Mapped[int] = mapped_column(Integer, default=0)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"))
    
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
    column_id: Mapped[int] = mapped_column(ForeignKey("columns.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    
    column: Mapped["Column"] = relationship(back_populates="tasks")
    assignee: Mapped["User"] = relationship(back_populates="tasks")