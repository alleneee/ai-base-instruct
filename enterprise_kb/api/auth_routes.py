"""用户认证路由模块"""
from fastapi import APIRouter, Depends, HTTPException

from enterprise_kb.models.users import (
    User,
    UserRead,
    UserCreate,
    UserUpdate,
    fastapi_users,
    jwt_backend,
    current_active_user,
    current_superuser,
)

# 创建路由器
router = APIRouter(
    prefix="/auth",
    tags=["认证与用户管理"],
)

# 添加认证路由
router.include_router(
    fastapi_users.get_auth_router(jwt_backend),
    prefix="/jwt",
)

# 添加注册路由
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
)

# 添加验证路由
router.include_router(
    fastapi_users.get_verify_router(UserRead),
)

# 添加用户路由
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
)

# 用户信息
@router.get("/me", response_model=UserRead, tags=["用户"])
async def get_user_me(user: User = Depends(current_active_user)):
    """获取当前用户信息"""
    return user

# 用户列表（仅管理员）
@router.get("/users/all", tags=["用户管理"])
async def get_all_users(user: User = Depends(current_superuser)):
    """获取所有用户（需要管理员权限）"""
    # 在实际应用中，这里应该从数据库获取用户列表
    return {"message": "此路由需实现用户列表查询"} 