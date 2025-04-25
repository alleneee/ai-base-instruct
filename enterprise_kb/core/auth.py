"""认证核心模块"""
import uuid
from typing import AsyncGenerator

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend, 
    BearerTransport, 
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.models.users import User
from enterprise_kb.db.session import get_async_session

# 获取用户数据库
async def get_user_db(session=Depends(get_async_session)) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    """获取用户数据库"""
    yield SQLAlchemyUserDatabase(session, User)


# 用户管理器
class UserManager(BaseUserManager[User, uuid.UUID]):
    """用户管理器"""
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY
    
    async def on_after_register(self, user: User, request=None):
        """注册后回调"""
        print(f"用户 {user.id} 已注册")


# 获取用户管理器
async def get_user_manager(user_db=Depends(get_user_db)) -> AsyncGenerator[UserManager, None]:
    """获取用户管理器"""
    yield UserManager(user_db)


# 认证后端
bearer_transport = BearerTransport(tokenUrl=f"{settings.API_PREFIX}/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    """获取JWT策略"""
    return JWTStrategy(
        secret=settings.SECRET_KEY, 
        lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        algorithm=settings.JWT_ALGORITHM,
    )


# JWT认证后端
jwt_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


# FastAPI用户集成
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [jwt_backend])


# 依赖项
current_active_user = fastapi_users.current_user(active=True)
current_active_verified_user = fastapi_users.current_user(active=True, verified=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True) 