"""
Данный файл содержит валидатор аутентификации, а также схемы
пользователя, задач, колонок и досок, соответствующих
классам из UML-Диаграммы класов.
"""


from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional, List, Any
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt
import bcrypt

if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type('About', (object,), {'__version__': bcrypt.__version__})

# --- SECURITY CONFIG (Конфигурация безопасности)---
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthHandler:
    @staticmethod
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password[:72], hashed_password)

    @staticmethod
    def get_password_hash(password):
        return pwd_context.hash(password[:72])

    @staticmethod
    def create_access_token(data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- USER SCHEMAS (Схемы пользователя) ---

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- TASK SCHEMAS (Схемы задач)---
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "Medium"

class TaskCreate(TaskBase):
    column_id: int

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None

class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    priority: Any
    column_id: int
    assignee_id: Optional[int] = None
    
    # Валидатор: преобразуем Enum или любой объект в строку
    @field_validator('priority', mode='before')
    @classmethod
    def transform_priority(cls, v: Any) -> str:
        if hasattr(v, 'value'):
            return str(v.value)
        return str(v) if v is not None else "Medium"

    model_config = ConfigDict(from_attributes=True)

# --- COLUMN SCHEMAS (Схемы колонок) ---
class ColumnCreate(BaseModel):
    title: str
    order: Optional[int] = 0

class ColumnUpdate(BaseModel):
    title: str

class ColumnRead(BaseModel):
    id: int
    title: str
    order: int
    tasks: List[TaskRead] = []
    model_config = ConfigDict(from_attributes=True)

# --- BOARD SCHEMAS (Схемы досок) ---
class BoardRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    owner_id: int
    columns: List[ColumnRead] = []
    model_config = ConfigDict(from_attributes=True)

class MemberInvite(BaseModel):
    email: EmailStr