"""
认证服务

提供用户认证、权限验证和JWT令牌管理功能
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from enterprise_kb.core.config import settings
from enterprise_kb.db.models.user import User, Role, Permission
from enterprise_kb.db.repositories.user import UserRepository, RoleRepository
from enterprise_kb.schemas.token import TokenData
from enterprise_kb.schemas.user import UserCreate, UserUpdate

# OAuth2 配置
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# JWT 配置
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES


class AuthService:
    """认证服务类，提供用户认证和权限验证功能"""
    
    def __init__(self, user_repo: UserRepository, role_repo: RoleRepository):
        self.user_repo = user_repo
        self.role_repo = role_repo

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )

    async def get_password_hash(self, password: str) -> str:
        """生成密码哈希"""
        return bcrypt.hashpw(
            password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """验证用户"""
        user = await self.user_repo.get_by_username(username)
        if not user:
            return None
        if not await self.verify_password(password, user.hashed_password):
            return None
        return user

    async def create_access_token(
        self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """创建JWT访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def get_current_user(
        self, token: str = Depends(oauth2_scheme)
    ) -> User:
        """获取当前用户"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无法验证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except (JWTError, ValidationError):
            raise credentials_exception
        
        user = await self.user_repo.get_by_username(token_data.username)
        if user is None:
            raise credentials_exception
        return user

    async def get_current_active_user(
        self, current_user: User = Depends(get_current_user)
    ) -> User:
        """获取当前活跃用户"""
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="账号未激活")
        return current_user

    async def check_permission(
        self, user: User, resource: str, action: str
    ) -> bool:
        """检查用户是否有权限执行特定操作"""
        # 超级管理员拥有所有权限
        if user.is_superuser:
            return True
            
        # 检查用户角色的权限
        user_with_roles = await self.user_repo.get_with_roles(user.id)
        if not user_with_roles or not user_with_roles.roles:
            return False
            
        for role in user_with_roles.roles:
            role_with_permissions = await self.role_repo.get_with_permissions(role.id)
            if not role_with_permissions or not role_with_permissions.permissions:
                continue
                
            for permission in role_with_permissions.permissions:
                if (permission.resource == resource or permission.resource == "*") and \
                   (permission.action == action or permission.action == "*"):
                    return True
                    
        return False

    async def register_user(self, user_create: UserCreate) -> User:
        """注册新用户"""
        # 检查用户是否已存在
        existing_user = await self.user_repo.get_by_username(user_create.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已被使用"
            )
            
        existing_email = await self.user_repo.get_by_email(user_create.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用"
            )
            
        # 创建新用户
        hashed_password = await self.get_password_hash(user_create.password)
        user_data = user_create.dict(exclude={"password"})
        user_data["hashed_password"] = hashed_password
        
        # 添加到默认角色
        default_role = await self.role_repo.get_by_name("user")
        if not default_role:
            # 如果默认角色不存在，则创建
            default_role = await self.role_repo.create(
                {"name": "user", "description": "普通用户"}
            )
            
        new_user = await self.user_repo.create(user_data)
        await self.user_repo.add_role(new_user.id, default_role.id)
        
        return new_user

    async def update_user(
        self, user_id: str, user_update: UserUpdate, current_user: User
    ) -> User:
        """更新用户信息"""
        # 权限检查 - 只允许用户更新自己的信息或超级管理员可以更新任何用户
        if user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
            
        user_data = user_update.dict(exclude_unset=True)
        
        # 如果更新包含密码，则哈希处理
        if "password" in user_data:
            user_data["hashed_password"] = await self.get_password_hash(user_data.pop("password"))
            
        updated_user = await self.user_repo.update(user_id, user_data)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
            
        return updated_user 