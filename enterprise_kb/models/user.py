from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    """用户基本信息模型"""
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    """创建用户的模型"""
    password: str

class UserLogin(BaseModel):
    """用户登录模型"""
    username: str
    password: str

class User(UserBase):
    """用户模型"""
    id: str
    roles: List[str] = []
    created_at: datetime
    
    class Config:
        orm_mode = True
