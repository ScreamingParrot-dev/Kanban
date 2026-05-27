"""
Данный файл содержит валидатор аутентификации, а также схемы
пользователя, задач, колонок и досок с учетом ролей.
"""

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional, List, Any
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt
import bcrypt

if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type('About', (object,), {'__version__': bcrypt.__version__})

SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthHandler:
    @staticmethod
    def verify_password(plain_password, hashed_password):
        try: 
            return pwd_context.verify(plain_password[:72], hashed_password)
        except Exception: 
            return False

    @staticmethod
    def get_password_hash(password):
        return pwd_context.hash(password[:72])

    @staticmethod
    def create_access_token(data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

# НОВАЯ СХЕМА: Только для входа
class UserLogin(BaseModel):
    username: str
    password: str

class UserRead(UserBase):
    id: int
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UserProfileUpdate(BaseModel):
    description: Optional[str] = None

class BoardMemberRead(BaseModel):
    user: UserRead
    role: Any
    @field_validator('role', mode='before')
    @classmethod
    def transform_role(cls, v: Any) -> str:
        return str(v.value) if hasattr(v, 'value') else str(v)
    model_config = ConfigDict(from_attributes=True)

class TaskAttachmentRead(BaseModel):
    id: int
    file_name: str
    file_url: str
    model_config = ConfigDict(from_attributes=True)

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "MEDIUM"

class TaskCreate(TaskBase):
    column_id: int
    assignee_id: Optional[int] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[int] = None

class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    priority: Any
    column_id: int
    assignee_id: Optional[int] = None
    assignee: Optional[UserRead] = None
    attachments: List[TaskAttachmentRead] = []
    
    @field_validator('priority', mode='before')
    @classmethod
    def transform_priority(cls, v: Any) -> str:
        return str(v.value) if hasattr(v, 'value') else (str(v) if v is not None else "MEDIUM")
    model_config = ConfigDict(from_attributes=True)

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

class BoardCreate(BaseModel):
    title: str
    description: Optional[str] = None

class BoardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class BoardRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    background_url: Optional[str] = None
    member_associations: List[BoardMemberRead] = []
    columns: List[ColumnRead] = []
    model_config = ConfigDict(from_attributes=True)

class MemberInvite(BaseModel):
    email: EmailStr
    role: str = "MEMBER"
    
class MemberRoleUpdate(BaseModel):
    role: str