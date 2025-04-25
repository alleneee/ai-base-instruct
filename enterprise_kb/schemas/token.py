"""
令牌相关的Pydantic模型

定义了JWT令牌相关的数据结构和验证规则
"""
from typing import List, Optional

from pydantic import BaseModel


class Token(BaseModel):
    """
    认证令牌模型
    
    Attributes:
        access_token: JWT访问令牌
        token_type: 令牌类型（通常为"bearer"）
        refresh_token: 刷新令牌
    """
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    """
    令牌数据模型
    
    Attributes:
        user_id: 用户ID
        username: 用户名
        scopes: 权限范围列表
        exp: 过期时间
    """
    user_id: Optional[int] = None
    username: Optional[str] = None
    scopes: List[str] = []
    exp: Optional[int] = None 