"""用户模型模块"""
import uuid
from typing import List, Optional, AsyncGenerator

from fastapi import Depends
from fastapi_users import schemas, BaseUserManager, FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend, 
    BearerTransport, 
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from pydantic import EmailStr
from sqlalchemy import String, Boolean, Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, Mapped, mapped_column

from enterprise_kb.config.database import Base, get_async_session
from enterprise_kb.config.settings import settings


# 用户模型
class User(SQLAlchemyBaseUserTableUUID, Base):
    """用户数据模型"""
    __tablename__ = "users"
    
    # 扩展字段
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # 角色和权限
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # 关系
    user_permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")


# 文档权限关联表
class UserPermission(Base):
    """用户文档权限"""
    __tablename__ = "user_permissions"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE")
    )
    document_id: Mapped[str] = mapped_column(String(50), nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=True)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 关系
    user = relationship("User", back_populates="user_permissions")


# 用户模式
class UserRead(schemas.BaseUser[uuid.UUID]):
    """用户读取模式"""
    full_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: bool = False


class UserCreate(schemas.BaseUserCreate):
    """用户创建模式"""
    full_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    is_admin: bool = False


class UserUpdate(schemas.BaseUserUpdate):
    """用户更新模式"""
    full_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    avatar_url: Optional[str] = None


# 获取用户数据库
async def get_user_db(session: AsyncSession = Depends(get_async_session)) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
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