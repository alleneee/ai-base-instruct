"""基础仓库模块"""
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from enterprise_kb.db.base import Base

T = TypeVar('T', bound=Base)

class BaseRepository(Generic[T]):
    """基础仓库类，提供通用的数据库操作"""
    
    model: Type[T] = None
    
    async def create(self, data: Dict[str, Any], session: AsyncSession) -> T:
        """
        创建记录
        
        Args:
            data: 创建数据
            session: 数据库会话
            
        Returns:
            创建的模型实例
        """
        instance = self.model(**data)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance
        
    async def get(self, id: Any, session: AsyncSession) -> Optional[T]:
        """
        根据ID获取记录
        
        Args:
            id: 记录ID
            session: 数据库会话
            
        Returns:
            模型实例，不存在则返回None
        """
        stmt = select(self.model).where(self.model.id == id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def list(
        self, 
        session: AsyncSession,
        skip: int = 0, 
        limit: int = 100
    ) -> List[T]:
        """
        获取记录列表
        
        Args:
            session: 数据库会话
            skip: 跳过数量
            limit: 限制数量
            
        Returns:
            模型实例列表
        """
        stmt = select(self.model).offset(skip).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()
        
    async def update(
        self, 
        id: Any, 
        data: Dict[str, Any], 
        session: AsyncSession
    ) -> Optional[T]:
        """
        更新记录
        
        Args:
            id: 记录ID
            data: 更新数据
            session: 数据库会话
            
        Returns:
            更新后的模型实例，不存在则返回None
        """
        instance = await self.get(id, session)
        if not instance:
            return None
            
        for key, value in data.items():
            setattr(instance, key, value)
            
        await session.commit()
        await session.refresh(instance)
        return instance
        
    async def delete(self, id: Any, session: AsyncSession) -> bool:
        """
        删除记录
        
        Args:
            id: 记录ID
            session: 数据库会话
            
        Returns:
            删除是否成功
        """
        instance = await self.get(id, session)
        if not instance:
            return False
            
        await session.delete(instance)
        await session.commit()
        return True 