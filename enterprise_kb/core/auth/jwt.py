"""JWT认证配置模块"""
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_kb.core.config.settings import settings
from enterprise_kb.models.user import User
from enterprise_kb.core.config.database import get_db

# JWT配置类
class JWTSettings(BaseModel):
    """JWT认证配置"""
    authjwt_secret_key: str = settings.JWT_SECRET_KEY
    authjwt_token_location: set = {"cookies", "headers"}
    authjwt_cookie_secure: bool = settings.PRODUCTION  # 生产环境必须开启
    authjwt_cookie_csrf_protect: bool = True
    authjwt_cookie_samesite: str = "lax"
    authjwt_access_token_expires: int = settings.JWT_ACCESS_TOKEN_EXPIRE
    authjwt_refresh_token_expires: int = settings.JWT_REFRESH_TOKEN_EXPIRE

# 加载JWT配置
@AuthJWT.load_config
def get_config():
    return JWTSettings()

# 注册异常处理器
def register_exception_handler(app: FastAPI):
    """注册JWT异常处理器"""
    @app.exception_handler(AuthJWTException)
    def authjwt_exception_handler(request: Request, exc: AuthJWTException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.message,
                "details": None
            }
        )

# 获取当前用户依赖
async def get_current_user(authorize: AuthJWT = Depends(), db: AsyncSession = Depends(get_db)):
    """获取当前用户
    
    使用JWT令牌验证当前用户并返回用户对象
    
    Args:
        authorize: JWT授权对象
        db: 数据库会话
        
    Returns:
        用户对象
    """
    try:
        # 验证令牌
        authorize.jwt_required()
        
        # 获取用户ID
        user_id = authorize.get_jwt_subject()
        
        # 从数据库获取用户信息
        from enterprise_kb.crud.user import get_user_by_id
        user = await get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="用户已停用")
        
        return user
    except AuthJWTException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message
        )

# 获取当前活跃用户依赖
async def get_current_active_user(user: User = Depends(get_current_user)):
    """获取当前活跃用户"""
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已停用")
    return user

# 角色检查函数
def has_roles(required_roles: List[str]):
    """创建角色检查依赖"""
    async def role_checker(authorize: AuthJWT = Depends(), user: User = Depends(get_current_user)):
        # 获取令牌中的角色信息
        jwt_data = authorize.get_raw_jwt()
        user_roles = jwt_data.get("roles", [])
        
        # 检查是否有所需角色
        for role in required_roles:
            if role in user_roles:
                return user
        
        # 没有所需角色，拒绝访问
        raise HTTPException(
            status_code=403,
            detail="权限不足，需要以下角色之一：" + ", ".join(required_roles)
        )
    
    return role_checker

# 令牌黑名单（实际项目应使用Redis）
blacklisted_tokens = set()

def blacklist_token(jti: str) -> None:
    """将令牌加入黑名单"""
    blacklisted_tokens.add(jti)

def is_token_blacklisted(jti: str) -> bool:
    """检查令牌是否在黑名单中"""
    return jti in blacklisted_tokens

# 设置令牌黑名单检查器
@AuthJWT.token_in_denylist_loader
def check_if_token_in_denylist(decrypted_token):
    jti = decrypted_token['jti']
    return is_token_blacklisted(jti)
