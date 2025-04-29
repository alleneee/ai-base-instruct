"""用户服务模块"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import logging

from enterprise_kb.models.user import User, UserCreate

# 获取日志记录器
logger = logging.getLogger(__name__)

# 模拟数据库 (实际项目中应使用真实数据库)
users_db = {}

async def get_user_by_id(user_id: str) -> Optional[User]:
    """通过ID获取用户
    
    Args:
        user_id: 用户ID
        
    Returns:
        用户对象或None
    """
    if user_id not in users_db:
        return None
    
    user_data = users_db[user_id]
    return User(
        id=user_id,
        username=user_data["username"],
        email=user_data["email"],
        full_name=user_data.get("full_name"),
        is_active=user_data.get("is_active", True),
        roles=user_data.get("roles", []),
        created_at=user_data.get("created_at", datetime.utcnow())
    )

async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """通过用户名获取用户
    
    Args:
        username: 用户名
        
    Returns:
        用户数据字典或None
    """
    for user_id, user_data in users_db.items():
        if user_data["username"] == username:
            return {**user_data, "id": user_id}
    
    return None

async def create_user(
    username: str,
    email: str,
    hashed_password: str,
    full_name: Optional[str] = None,
    roles: List[str] = []
) -> User:
    """创建新用户
    
    Args:
        username: 用户名
        email: 电子邮件
        hashed_password: 哈希后的密码
        full_name: 全名
        roles: 角色列表
        
    Returns:
        创建的用户对象
    """
    # 生成唯一ID
    user_id = str(uuid.uuid4())
    
    # 创建用户数据
    user_data = {
        "username": username,
        "email": email,
        "full_name": full_name,
        "hashed_password": hashed_password,
        "is_active": True,
        "roles": roles,
        "created_at": datetime.utcnow()
    }
    
    # 保存到数据库
    users_db[user_id] = user_data
    logger.info(f"已创建用户: {username}")
    
    # 返回用户对象
    return User(
        id=user_id,
        username=username,
        email=email,
        full_name=full_name,
        is_active=True,
        roles=roles,
        created_at=user_data["created_at"]
    )

async def update_user(user_id: str, user_data: Dict[str, Any]) -> Optional[User]:
    """更新用户信息
    
    Args:
        user_id: 用户ID
        user_data: 要更新的用户数据
        
    Returns:
        更新后的用户对象或None
    """
    if user_id not in users_db:
        return None
        
    # 更新数据，但保留敏感字段
    current_data = users_db[user_id]
    for key, value in user_data.items():
        if key != "hashed_password" and key != "created_at":  # 不直接更新密码和创建时间
            current_data[key] = value
            
    # 保存更新后的数据
    users_db[user_id] = current_data
    logger.info(f"已更新用户: {current_data['username']}")
    
    # 返回更新后的用户对象
    return await get_user_by_id(user_id)

async def delete_user(user_id: str) -> bool:
    """删除用户
    
    Args:
        user_id: 用户ID
        
    Returns:
        是否成功删除
    """
    if user_id not in users_db:
        return False
        
    # 从数据库中删除
    deleted_user = users_db.pop(user_id)
    logger.info(f"已删除用户: {deleted_user['username']}")
    
    return True

async def list_users(skip: int = 0, limit: int = 100) -> List[User]:
    """列出用户
    
    Args:
        skip: 跳过的记录数
        limit: 返回的最大记录数
        
    Returns:
        用户对象列表
    """
    users = []
    for user_id, user_data in list(users_db.items())[skip:skip+limit]:
        users.append(
            User(
                id=user_id,
                username=user_data["username"],
                email=user_data["email"],
                full_name=user_data.get("full_name"),
                is_active=user_data.get("is_active", True),
                roles=user_data.get("roles", []),
                created_at=user_data.get("created_at", datetime.utcnow())
            )
        )
    
    return users
