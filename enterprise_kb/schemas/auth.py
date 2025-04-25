"""认证模式(Schema)模块"""
import uuid
from typing import Optional

from fastapi_users import schemas
from pydantic import BaseModel, EmailStr


class UserRead(schemas.BaseUser[uuid.UUID]):
    """用户读取模式"""
    full_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: bool = False


class UserCreate(schemas.BaseUserCreate):
    """用户创建模式"""
    full_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    is_admin: bool = False


class UserUpdate(schemas.BaseUserUpdate):
    """用户更新模式"""
    full_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    avatar_url: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str
    status_code: int
    error_type: Optional[str] = None 