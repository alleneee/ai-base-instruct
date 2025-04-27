"""文档仓库模块"""
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_kb.db.models.documents import DocumentModel
from enterprise_kb.models.schemas import DocumentStatus
from enterprise_kb.db.session import get_session

class DocumentRepository:
    """文档仓库，处理文档数据库操作"""
    
    async def create(self, document_data: Dict[str, Any]) -> str:
        """
        创建文档
        
        Args:
            document_data: 文档数据
            
        Returns:
            创建的文档ID
        """
        async with get_session() as session:
            document = DocumentModel(**document_data)
            session.add(document)
            await session.commit()
            await session.refresh(document)
            return document.id
            
    async def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            文档数据，如果不存在则返回None
        """
        async with get_session() as session:
            result = await session.execute(
                select(DocumentModel).where(DocumentModel.id == doc_id)
            )
            document = result.scalars().first()
            
            if not document:
                return None
                
            return self._model_to_dict(document)
            
    async def update(self, doc_id: str, update_data: Dict[str, Any]) -> bool:
        """
        更新文档
        
        Args:
            doc_id: 文档ID
            update_data: 更新数据
            
        Returns:
            更新是否成功
        """
        async with get_session() as session:
            result = await session.execute(
                update(DocumentModel)
                .where(DocumentModel.id == doc_id)
                .values(**update_data)
            )
            await session.commit()
            
            return result.rowcount > 0
            
    async def update_status(self, doc_id: str, status: DocumentStatus, error: Optional[str] = None) -> bool:
        """
        更新文档状态
        
        Args:
            doc_id: 文档ID
            status: 新状态
            error: 错误信息，如果有
            
        Returns:
            更新是否成功
        """
        update_data = {
            "status": status,
            "updated_at": datetime.now()
        }
        
        if error:
            update_data["error"] = error
            
        return await self.update(doc_id, update_data)
            
    async def delete(self, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            删除是否成功
        """
        async with get_session() as session:
            result = await session.execute(
                delete(DocumentModel).where(DocumentModel.id == doc_id)
            )
            await session.commit()
            
            return result.rowcount > 0
            
    async def get_many(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取多个文档
        
        Args:
            skip: 跳过数量
            limit: 限制数量
            filters: 过滤条件
            
        Returns:
            文档列表和总数
        """
        filters = filters or {}
        
        async with get_session() as session:
            # 构建查询
            query = select(DocumentModel)
            count_query = select(func.count()).select_from(DocumentModel)
            
            # 应用过滤条件
            for field, value in filters.items():
                if hasattr(DocumentModel, field):
                    query = query.where(getattr(DocumentModel, field) == value)
                    count_query = count_query.where(getattr(DocumentModel, field) == value)
            
            # 执行总数查询
            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0
            
            # 执行分页查询
            query = query.order_by(DocumentModel.updated_at.desc())
            query = query.offset(skip).limit(limit)
            
            result = await session.execute(query)
            documents = result.scalars().all()
            
            return [self._model_to_dict(doc) for doc in documents], total
    
    def _model_to_dict(self, model: DocumentModel) -> Dict[str, Any]:
        """
        将模型对象转换为字典
        
        Args:
            model: 模型对象
            
        Returns:
            字典表示
        """
        return {
            "id": model.id,
            "file_name": model.file_name,
            "file_path": model.file_path,
            "file_type": model.file_type,
            "title": model.title,
            "description": model.description,
            "status": model.status,
            "error": model.error,
            "size_bytes": model.size_bytes,
            "node_count": model.node_count,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
            "metadata": model.metadata
        } 