"""
用户和角色数据库仓库

提供用户和角色数据的CRUD操作
"""
from typing import Dict, List, Optional, Any, Union
import uuid

from sqlalchemy import select, insert, update, delete
from sqlalchemy.orm import Session, selectinload

from enterprise_kb.db.models.user import User, Role, Permission, user_role


class BaseRepository:
    """基础仓库类"""
    
    def __init__(self, db_session: Session):
        self.db = db_session


class UserRepository(BaseRepository):
    """用户仓库类"""
    
    async def create(self, user_data: Dict[str, Any]) -> User:
        """创建用户"""
        user_id = str(uuid.uuid4())
        new_user = User(id=user_id, **user_data)
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user
    
    async def get(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return self.db.query(User).filter(User.username == username).first()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return self.db.query(User).filter(User.email == email).first()
    
    async def get_with_roles(self, user_id: str) -> Optional[User]:
        """获取用户及其角色"""
        return self.db.query(User)\
            .options(selectinload(User.roles))\
            .filter(User.id == user_id)\
            .first()
    
    async def list(self, skip: int = 0, limit: int = 100) -> List[User]:
        """获取用户列表"""
        return self.db.query(User).offset(skip).limit(limit).all()
    
    async def update(self, user_id: str, user_data: Dict[str, Any]) -> Optional[User]:
        """更新用户"""
        result = self.db.query(User)\
            .filter(User.id == user_id)\
            .update(user_data)
        self.db.commit()
        
        if result:
            return await self.get(user_id)
        return None
    
    async def delete(self, user_id: str) -> bool:
        """删除用户"""
        result = self.db.query(User)\
            .filter(User.id == user_id)\
            .delete()
        self.db.commit()
        return bool(result)
    
    async def add_role(self, user_id: str, role_id: str) -> bool:
        """为用户添加角色"""
        user = await self.get(user_id)
        role = await RoleRepository(self.db).get(role_id)
        
        if not user or not role:
            return False
        
        # 检查是否已经存在关联
        stmt = select(user_role).where(
            user_role.c.user_id == user_id,
            user_role.c.role_id == role_id
        )
        existing = self.db.execute(stmt).first()
        
        if not existing:
            # 插入新的关联
            stmt = insert(user_role).values(
                user_id=user_id,
                role_id=role_id
            )
            self.db.execute(stmt)
            self.db.commit()
        
        return True
    
    async def remove_role(self, user_id: str, role_id: str) -> bool:
        """为用户移除角色"""
        stmt = delete(user_role).where(
            user_role.c.user_id == user_id,
            user_role.c.role_id == role_id
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount > 0


class RoleRepository(BaseRepository):
    """角色仓库类"""
    
    async def create(self, role_data: Dict[str, Any]) -> Role:
        """创建角色"""
        role_id = str(uuid.uuid4())
        new_role = Role(id=role_id, **role_data)
        self.db.add(new_role)
        self.db.commit()
        self.db.refresh(new_role)
        return new_role
    
    async def get(self, role_id: str) -> Optional[Role]:
        """根据ID获取角色"""
        return self.db.query(Role).filter(Role.id == role_id).first()
    
    async def get_by_name(self, name: str) -> Optional[Role]:
        """根据名称获取角色"""
        return self.db.query(Role).filter(Role.name == name).first()
    
    async def get_with_permissions(self, role_id: str) -> Optional[Role]:
        """获取角色及其权限"""
        return self.db.query(Role)\
            .options(selectinload(Role.permissions))\
            .filter(Role.id == role_id)\
            .first()
    
    async def list(self, skip: int = 0, limit: int = 100) -> List[Role]:
        """获取角色列表"""
        return self.db.query(Role).offset(skip).limit(limit).all()
    
    async def update(self, role_id: str, role_data: Dict[str, Any]) -> Optional[Role]:
        """更新角色"""
        result = self.db.query(Role)\
            .filter(Role.id == role_id)\
            .update(role_data)
        self.db.commit()
        
        if result:
            return await self.get(role_id)
        return None
    
    async def delete(self, role_id: str) -> bool:
        """删除角色"""
        result = self.db.query(Role)\
            .filter(Role.id == role_id)\
            .delete()
        self.db.commit()
        return bool(result)
    
    async def add_permission(self, role_id: str, permission_data: Dict[str, Any]) -> Permission:
        """为角色添加权限"""
        permission_id = str(uuid.uuid4())
        new_permission = Permission(
            id=permission_id,
            role_id=role_id,
            **permission_data
        )
        self.db.add(new_permission)
        self.db.commit()
        self.db.refresh(new_permission)
        return new_permission
    
    async def remove_permission(self, permission_id: str) -> bool:
        """移除权限"""
        result = self.db.query(Permission)\
            .filter(Permission.id == permission_id)\
            .delete()
        self.db.commit()
        return bool(result) 