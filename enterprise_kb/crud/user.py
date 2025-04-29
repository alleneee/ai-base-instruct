"""用户CRUD操作"""
import uuid
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from enterprise_kb.models.database.user import User, Role, user_role

async def get_user_by_id(db: AsyncSession, user_id: Union[str, uuid.UUID]) -> Optional[User]:
    """通过ID获取用户
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        用户对象或None
    """
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
        
    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """通过用户名获取用户
    
    Args:
        db: 数据库会话
        username: 用户名
        
    Returns:
        用户对象或None
    """
    stmt = select(User).options(selectinload(User.roles)).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """通过电子邮件获取用户
    
    Args:
        db: 数据库会话
        email: 电子邮件
        
    Returns:
        用户对象或None
    """
    stmt = select(User).options(selectinload(User.roles)).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    hashed_password: str,
    full_name: Optional[str] = None,
    is_active: bool = True,
    is_superuser: bool = False,
    role_ids: Optional[List[uuid.UUID]] = None
) -> User:
    """创建新用户
    
    Args:
        db: 数据库会话
        username: 用户名
        email: 电子邮件
        hashed_password: 哈希密码
        full_name: 用户全名
        is_active: 是否激活
        is_superuser: 是否超级用户
        role_ids: 角色ID列表
        
    Returns:
        创建的用户对象
    """
    # 创建用户对象
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        is_active=is_active,
        is_superuser=is_superuser
    )
    
    # 添加角色（如果有）
    if role_ids:
        stmt = select(Role).where(Role.id.in_(role_ids))
        result = await db.execute(stmt)
        roles = result.scalars().all()
        user.roles = roles
    else:
        # 为新用户添加默认"user"角色
        stmt = select(Role).where(Role.name == "user")
        result = await db.execute(stmt)
        default_role = result.scalar_one_or_none()
        
        if default_role:
            user.roles = [default_role]
        else:
            # 如果没有默认角色，创建它
            default_role = Role(name="user", description="普通用户角色")
            db.add(default_role)
            await db.flush()
            user.roles = [default_role]
    
    # 添加用户到数据库
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user

async def update_user(
    db: AsyncSession,
    user_id: Union[str, uuid.UUID],
    data: Dict[str, Any]
) -> Optional[User]:
    """更新用户信息
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        data: 更新数据
        
    Returns:
        更新后的用户对象或None
    """
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    
    # 获取用户
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    
    # 更新角色（如需要）
    if "role_ids" in data:
        role_ids = data.pop("role_ids")
        stmt = select(Role).where(Role.id.in_(role_ids))
        result = await db.execute(stmt)
        roles = result.scalars().all()
        user.roles = roles
    
    # 更新用户其他属性
    for key, value in data.items():
        if hasattr(user, key) and key != "id" and key != "roles":
            setattr(user, key, value)
    
    # 更新数据库
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user

async def delete_user(db: AsyncSession, user_id: Union[str, uuid.UUID]) -> bool:
    """删除用户
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        是否成功删除
    """
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    
    # 删除用户
    stmt = delete(User).where(User.id == user_id)
    result = await db.execute(stmt)
    await db.commit()
    
    # 检查是否成功删除
    return result.rowcount > 0

async def list_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[User]:
    """列出用户
    
    Args:
        db: 数据库会话
        skip: 跳过的记录数
        limit: 返回的最大记录数
        
    Returns:
        用户列表
    """
    stmt = select(User).options(selectinload(User.roles)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_last_login(db: AsyncSession, user_id: Union[str, uuid.UUID]) -> bool:
    """更新用户最后登录时间
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        是否成功更新
    """
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    
    stmt = update(User).where(User.id == user_id).values(last_login=datetime.utcnow())
    result = await db.execute(stmt)
    await db.commit()
    
    return result.rowcount > 0
