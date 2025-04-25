"""
认证API端点

提供用户注册、登录和令牌刷新功能
"""
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.database import get_db
from enterprise_kb.db.repositories.user import UserRepository, RoleRepository
from enterprise_kb.schemas.token import Token
from enterprise_kb.schemas.user import UserCreate, User
from enterprise_kb.services.auth import AuthService

router = APIRouter()


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
) -> Any:
    """
    注册新用户
    """
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    auth_service = AuthService(user_repo, role_repo)
    
    return await auth_service.register_user(user_data)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Any:
    """
    用户登录并获取JWT令牌
    """
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    auth_service = AuthService(user_repo, role_repo)
    
    user = await auth_service.authenticate_user(
        form_data.username, form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": user.username,
        "user_id": user.id,
    }
    access_token = await auth_service.create_access_token(
        data=token_data, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    } 