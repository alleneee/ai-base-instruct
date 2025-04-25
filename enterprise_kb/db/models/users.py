"""用户数据库模型模块"""
import uuid
from typing import Optional, List

from sqlalchemy import String, Boolean, ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID

from enterprise_kb.db.base import Base


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