"""角色CRUD操作"""
import uuid
from typing import List, Optional, Union, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from enterprise_kb.models.database.user import Role, User

async def get_role_by_id(db: AsyncSession, role_id: Union[str, uuid.UUID]) -> Optional[Role]:
    """通过ID获取角色
    
    Args:
        db: 数据库会话
        role_id: 角色ID
        
    Returns:
        角色对象或None
    """
    if isinstance(role_id, str):
        role_id = uuid.UUID(role_id)
        
    stmt = select(Role).where(Role.id == role_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_role_by_name(db: AsyncSession, name: str) -> Optional[Role]:
    """通过名称获取角色
    
    Args:
        db: 数据库会话
        name: 角色名称
        
    Returns:
        角色对象或None
    """
    stmt = select(Role).where(Role.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create_role(
    db: AsyncSession,
    name: str,
    description: Optional[str] = None
) -> Role:
    """创建新角色
    
    Args:
        db: 数据库会话
        name: 角色名称
        description: 角色描述
        
    Returns:
        创建的角色对象
    """
    # 创建角色对象
    role = Role(
        name=name,
        description=description or f"{name}角色"
    )
    
    # 添加角色到数据库
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    return role

async def update_role(
    db: AsyncSession,
    role_id: Union[str, uuid.UUID],
    data: Dict[str, Any]
) -> Optional[Role]:
    """更新角色信息
    
    Args:
        db: 数据库会话
        role_id: 角色ID
        data: 更新数据
        
    Returns:
        更新后的角色对象或None
    """
    if isinstance(role_id, str):
        role_id = uuid.UUID(role_id)
    
    # 获取角色
    role = await get_role_by_id(db, role_id)
    if not role:
        return None
    
    # 更新角色属性
    for key, value in data.items():
        if hasattr(role, key) and key != "id":
            setattr(role, key, value)
    
    # 更新数据库
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    return role

async def delete_role(db: AsyncSession, role_id: Union[str, uuid.UUID]) -> bool:
    """删除角色
    
    Args:
        db: 数据库会话
        role_id: 角色ID
        
    Returns:
        是否成功删除
    """
    if isinstance(role_id, str):
        role_id = uuid.UUID(role_id)
    
    # 删除角色
    stmt = delete(Role).where(Role.id == role_id)
    result = await db.execute(stmt)
    await db.commit()
    
    # 检查是否成功删除
    return result.rowcount > 0

async def list_roles(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[Role]:
    """列出角色
    
    Args:
        db: 数据库会话
        skip: 跳过的记录数
        limit: 返回的最大记录数
        
    Returns:
        角色列表
    """
    stmt = select(Role).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def assign_role_to_user(
    db: AsyncSession,
    user_id: Union[str, uuid.UUID],
    role_id: Union[str, uuid.UUID]
) -> bool:
    """将角色分配给用户
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        role_id: 角色ID
        
    Returns:
        是否成功分配
    """
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    if isinstance(role_id, str):
        role_id = uuid.UUID(role_id)
    
    # 获取用户和角色
    stmt_user = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    result_user = await db.execute(stmt_user)
    user = result_user.scalar_one_or_none()
    
    stmt_role = select(Role).where(Role.id == role_id)
    result_role = await db.execute(stmt_role)
    role = result_role.scalar_one_or_none()
    
    if not user or not role:
        return False
    
    # 检查用户是否已有该角色
    if role in user.roles:
        return True
    
    # 添加角色
    user.roles.append(role)
    await db.commit()
    
    return True

async def remove_role_from_user(
    db: AsyncSession,
    user_id: Union[str, uuid.UUID],
    role_id: Union[str, uuid.UUID]
) -> bool:
    """从用户移除角色
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        role_id: 角色ID
        
    Returns:
        是否成功移除
    """
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    if isinstance(role_id, str):
        role_id = uuid.UUID(role_id)
    
    # 获取用户和角色
    stmt_user = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    result_user = await db.execute(stmt_user)
    user = result_user.scalar_one_or_none()
    
    stmt_role = select(Role).where(Role.id == role_id)
    result_role = await db.execute(stmt_role)
    role = result_role.scalar_one_or_none()
    
    if not user or not role:
        return False
    
    # 检查用户是否有该角色
    if role not in user.roles:
        return True
    
    # 移除角色
    user.roles.remove(role)
    await db.commit()
    
    return True
