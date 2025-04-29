"""认证服务模块"""
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_kb.models.user import User, UserCreate
from enterprise_kb.crud.user import get_user_by_username, create_user, update_last_login
from enterprise_kb.crud.role import get_role_by_name

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
        
    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """获取密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """认证用户
    
    Args:
        db: 数据库会话
        username: 用户名
        password: 密码
        
    Returns:
        认证成功返回用户对象，失败返回None
    """
    # 获取用户
    user = await get_user_by_username(db, username)
    if not user:
        return None
    
    # 验证密码
    if not verify_password(password, user.hashed_password):
        return None
    
    # 更新最后登录时间
    await update_last_login(db, user.id)
    
    return user

async def register_user(db: AsyncSession, user_data: UserCreate) -> User:
    """注册新用户
    
    Args:
        db: 数据库会话
        user_data: 用户创建数据
        
    Returns:
        创建的用户对象
    """
    # 哈希密码
    hashed_password = get_password_hash(user_data.password)
    
    # 创建用户
    user = await create_user(
        db=db,
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name
    )
    
    return user

async def ensure_default_roles(db: AsyncSession) -> None:
    """确保默认角色存在
    
    创建系统需要的默认角色（如果不存在）
    
    Args:
        db: 数据库会话
    """
    # 确保基本角色存在
    default_roles = [
        {"name": "user", "description": "普通用户角色"},
        {"name": "admin", "description": "管理员角色"},
        {"name": "editor", "description": "编辑角色"}
    ]
    
    for role_data in default_roles:
        role = await get_role_by_name(db, role_data["name"])
        if not role:
            from enterprise_kb.crud.role import create_role
            await create_role(db, role_data["name"], role_data["description"])

async def get_user_roles(user: User) -> list[str]:
    """获取用户角色名称列表
    
    Args:
        user: 用户对象
        
    Returns:
        角色名称列表
    """
    return [role.name for role in user.roles] if user.roles else []
