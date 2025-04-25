"""
用户相关的Pydantic模型

定义了用户相关的数据结构和验证规则
"""
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    """
    用户基础模型
    
    Attributes:
        username: 用户名
        email: 电子邮件
        is_active: 是否激活
    """
    username: str
    email: EmailStr
    is_active: bool = True


class UserCreate(UserBase):
    """
    用户创建模型
    
    Attributes:
        password: 密码
        confirm_password: 确认密码
        role_ids: 角色ID列表
    """
    password: str = Field(..., min_length=8)
    confirm_password: str
    role_ids: List[int] = []
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('密码不匹配')
        return v


class UserUpdate(BaseModel):
    """
    用户更新模型
    
    Attributes:
        username: 用户名
        email: 电子邮件
        is_active: 是否激活
        role_ids: 角色ID列表
    """
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    role_ids: Optional[List[int]] = None
    password: Optional[str] = Field(None, min_length=8)


class UserInDB(UserBase):
    """
    数据库中的用户模型
    
    Attributes:
        id: 用户ID
        hashed_password: 哈希后的密码
    """
    id: int
    hashed_password: str
    
    class Config:
        orm_mode = True


class User(UserBase):
    """
    用户响应模型
    
    Attributes:
        id: 用户ID
        roles: 角色列表
    """
    id: int
    roles: List[str] = []
    
    class Config:
        orm_mode = True 