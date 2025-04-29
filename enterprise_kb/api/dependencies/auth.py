"""认证和授权依赖管理模块"""
from enum import Enum
from typing import Annotated, List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from enterprise_kb.models.users import User, current_active_user
from enterprise_kb.config.settings import settings

# OAuth2认证方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/token")

# 权限级别枚举
class PermissionLevel(str, Enum):
    """权限级别枚举"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

# 权限依赖函数
async def check_permissions(
    required_permissions: List[str],
    user: User = Depends(current_active_user)
) -> User:
    """
    检查用户是否拥有所需权限
    
    Args:
        required_permissions: 所需权限列表
        user: 当前活跃用户
        
    Returns:
        通过权限检查的用户对象
        
    Raises:
        HTTPException: 如果用户没有所需权限
    """
    # 管理员用户拥有所有权限
    if user.is_superuser:
        return user
        
    # 获取用户权限（假设用户对象中有permissions字段）
    user_permissions = getattr(user, "permissions", [])
    
    # 检查用户是否拥有所需权限
    if not all(perm in user_permissions for perm in required_permissions):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有足够的权限执行此操作"
        )
        
    return user

# 预定义权限检查依赖
async def require_read_permission(user: User = Depends(current_active_user)) -> User:
    """要求读取权限"""
    return await check_permissions([PermissionLevel.READ], user)

async def require_write_permission(user: User = Depends(current_active_user)) -> User:
    """要求写入权限"""
    return await check_permissions([PermissionLevel.WRITE], user)

async def require_admin_permission(user: User = Depends(current_active_user)) -> User:
    """要求管理员权限"""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此操作需要管理员权限"
        )
    return user

# 通用依赖类型
ActiveUser = Annotated[User, Depends(current_active_user)]
UserWithReadPerm = Annotated[User, Depends(require_read_permission)]
UserWithWritePerm = Annotated[User, Depends(require_write_permission)]
AdminUser = Annotated[User, Depends(require_admin_permission)]

# API密钥验证
async def verify_api_key(api_key: Optional[str] = None) -> bool:
    """
    验证API密钥
    
    Args:
        api_key: API密钥
        
    Returns:
        验证是否成功
        
    Raises:
        HTTPException: 如果API密钥无效
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供API密钥"
        )
        
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API密钥无效"
        )
        
    return True 