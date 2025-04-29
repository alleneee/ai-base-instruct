"""认证API接口"""
from fastapi import APIRouter, Depends, HTTPException, Response, Body
from fastapi_jwt_auth import AuthJWT
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_kb.models.user import UserLogin, UserCreate, User
from enterprise_kb.services.auth_service import authenticate_user, register_user, ensure_default_roles, get_user_roles
from enterprise_kb.core.auth.jwt import get_current_user
from enterprise_kb.core.config.database import get_db
from enterprise_kb.crud.user import get_user_by_username, get_user_by_email

router = APIRouter(
    prefix="/auth",
    tags=["认证"]
)

@router.post("/login")
async def login(
    user_login: UserLogin, 
    authorize: AuthJWT = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """用户登录
    
    验证用户名和密码，成功返回JWT令牌
    """
    # 认证用户
    user = await authenticate_user(db, user_login.username, user_login.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 获取用户角色列表
    roles = await get_user_roles(user)
    
    # 创建令牌
    access_token = authorize.create_access_token(
        subject=str(user.id),
        user_claims={
            "username": user.username,
            "email": user.email,
            "roles": roles
        }
    )
    
    refresh_token = authorize.create_refresh_token(
        subject=str(user.id)
    )
    
    # 创建响应
    response = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "roles": roles
        }
    }
    
    # 如果配置了cookie，设置cookie
    if "cookies" in authorize._token_location:
        response_obj = Response()
        authorize.set_access_cookies(access_token, response_obj)
        authorize.set_refresh_cookies(refresh_token, response_obj)
        
        # 添加响应数据
        for key, value in response.items():
            if key != "user":
                response_obj.headers[f"X-{key}"] = value
            
        return response_obj
    
    return response

@router.post("/refresh")
async def refresh(authorize: AuthJWT = Depends()):
    """刷新访问令牌
    
    使用刷新令牌获取新的访问令牌
    """
    authorize.jwt_refresh_token_required()
    
    # 获取当前用户ID
    current_user_id = authorize.get_jwt_subject()
    
    # 创建新的访问令牌
    new_access_token = authorize.create_access_token(subject=current_user_id)
    
    # 创建响应
    response = {
        "access_token": new_access_token,
        "token_type": "bearer"
    }
    
    # 如果配置了cookie，设置cookie
    if "cookies" in authorize._token_location:
        response_obj = Response()
        authorize.set_access_cookies(new_access_token, response_obj)
        
        # 添加响应数据
        for key, value in response.items():
            response_obj.headers[f"X-{key}"] = value
            
        return response_obj
    
    return response

@router.post("/logout")
async def logout(authorize: AuthJWT = Depends()):
    """用户登出
    
    使当前会话的令牌失效
    """
    authorize.jwt_required()
    
    # 将当前令牌加入黑名单
    jti = authorize.get_raw_jwt()["jti"]
    from enterprise_kb.core.auth.jwt import blacklist_token
    blacklist_token(jti)
    
    # 如果配置了cookie，清除cookie
    if "cookies" in authorize._token_location:
        response = Response()
        authorize.unset_jwt_cookies(response)
        return response
    
    return {"message": "成功登出"}

@router.post("/register", response_model=User)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """注册新用户
    
    创建新的用户账户
    """
    # 确保默认角色存在
    await ensure_default_roles(db)
    
    # 检查用户名是否已存在
    existing_user = await get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
        
    # 检查邮箱是否已存在
    existing_email = await get_user_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    # 注册用户
    user = await register_user(db, user_data)
    return user

@router.get("/me", response_model=User)
async def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息
    
    返回当前已认证用户的信息
    """
    return user
