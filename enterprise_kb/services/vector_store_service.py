"""
向量数据库服务模块
提供统一的向量数据库操作服务，包括创建集合、存储和检索向量等功能
"""
from typing import Dict, List, Optional, Any, Union
import logging
from functools import lru_cache

from enterprise_kb.storage.vector_store.base import VectorStoreBase
from enterprise_kb.storage.vector_store.factory import VectorStoreFactory
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

class VectorStoreService:
    """
    向量数据库服务类
    
    提供统一的向量数据库操作接口，底层使用不同的向量数据库实现
    """
    
    def __init__(self, 
                vector_store_type: Optional[str] = None,
                vector_store_config: Optional[Dict[str, Any]] = None):
        """
        初始化向量数据库服务
        
        Args:
            vector_store_type: 向量数据库类型，如果不提供则使用配置文件中的值
            vector_store_config: 向量数据库配置，如果不提供则使用配置文件中的值
        """
        self.vector_store_type = vector_store_type or settings.VECTOR_STORE_TYPE
        self.vector_store_config = vector_store_config
        self._vector_store = None
    
    async def get_vector_store(self) -> VectorStoreBase:
        """
        获取向量数据库实例
        
        Returns:
            VectorStoreBase: 向量数据库实例
        """
        if self._vector_store is None:
            self._vector_store = VectorStoreFactory.get_vector_store(
                store_type=self.vector_store_type,
                config=self.vector_store_config
            )
            # 初始化连接
            await self._vector_store.initialize()
        
        return self._vector_store
    
    async def create_collection(self, 
                              collection_name: str, 
                              dimension: int = 1536,
                              metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        创建向量集合
        
        Args:
            collection_name: 集合名称
            dimension: 向量维度，默认为1536（OpenAI text-embedding-3-small默认维度）
            metadata: 集合元数据
            
        Returns:
            bool: 创建是否成功
        """
        vector_store = await self.get_vector_store()
        return await vector_store.create_collection(
            collection_name=collection_name,
            dimension=dimension,
            metadata=metadata
        )
    
    async def drop_collection(self, collection_name: str) -> bool:
        """
        删除向量集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 删除是否成功
        """
        vector_store = await self.get_vector_store()
        return await vector_store.drop_collection(collection_name=collection_name)
    
    async def has_collection(self, collection_name: str) -> bool:
        """
        检查集合是否存在
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 集合是否存在
        """
        vector_store = await self.get_vector_store()
        return await vector_store.has_collection(collection_name=collection_name)
    
    async def list_collections(self) -> List[str]:
        """
        列出所有集合名称
        
        Returns:
            List[str]: 集合名称列表
        """
        vector_store = await self.get_vector_store()
        return await vector_store.list_collections()
    
    async def insert(self,
                    collection_name: str,
                    vectors: List[List[float]],
                    ids: Optional[List[str]] = None,
                    metadata: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """
        向集合中插入向量
        
        Args:
            collection_name: 集合名称
            vectors: 向量数据列表
            ids: 向量ID列表，如果不提供则自动生成
            metadata: 向量元数据列表
            
        Returns:
            List[str]: 插入的向量ID列表
        """
        vector_store = await self.get_vector_store()
        return await vector_store.insert(
            collection_name=collection_name,
            vectors=vectors,
            ids=ids,
            metadata=metadata
        )
    
    async def search(self,
                    collection_name: str,
                    query_vector: List[float],
                    limit: int = 10,
                    filter_expr: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        向量相似度搜索
        
        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            limit: 返回结果数量限制
            filter_expr: 过滤表达式
            
        Returns:
            List[Dict[str, Any]]: 搜索结果，包含id、score和metadata
        """
        vector_store = await self.get_vector_store()
        return await vector_store.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            filter_expr=filter_expr
        )
    
    async def delete(self, collection_name: str, ids: List[str]) -> bool:
        """
        删除指定ID的向量
        
        Args:
            collection_name: 集合名称
            ids: 要删除的向量ID列表
            
        Returns:
            bool: 删除是否成功
        """
        vector_store = await self.get_vector_store()
        return await vector_store.delete(
            collection_name=collection_name,
            ids=ids
        )
    
    async def count(self, collection_name: str, filter_expr: Optional[str] = None) -> int:
        """
        计算集合中的向量数量
        
        Args:
            collection_name: 集合名称
            filter_expr: 过滤表达式
            
        Returns:
            int: 向量数量
        """
        vector_store = await self.get_vector_store()
        return await vector_store.count(
            collection_name=collection_name,
            filter_expr=filter_expr
        )
    
    async def get(self, collection_name: str, ids: List[str]) -> List[Dict[str, Any]]:
        """
        获取指定ID的向量
        
        Args:
            collection_name: 集合名称
            ids: 向量ID列表
            
        Returns:
            List[Dict[str, Any]]: 向量数据列表，包含id、vector和metadata
        """
        vector_store = await self.get_vector_store()
        return await vector_store.get(
            collection_name=collection_name,
            ids=ids
        )
    
    async def close(self) -> None:
        """关闭向量数据库连接"""
        if self._vector_store is not None:
            await self._vector_store.close()
            self._vector_store = None


@lru_cache()
def get_vector_store_service() -> VectorStoreService:
    """
    获取向量数据库服务单例
    
    Returns:
        VectorStoreService: 向量数据库服务实例
    """
    return VectorStoreService() 