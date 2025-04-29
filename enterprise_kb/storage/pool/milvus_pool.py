"""
Milvus向量数据库连接池实现
"""
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
import time
from pymilvus import connections, Collection, utility

from enterprise_kb.storage.pool.base import ConnectionPool, BatchProcessor, PoolConfig
from enterprise_kb.utils.milvus_client import MilvusClient
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)


class MilvusPoolConfig(PoolConfig):
    """Milvus连接池配置"""
    
    def __init__(
        self,
        host: str = settings.MILVUS_HOST,
        port: int = settings.MILVUS_PORT,
        user: str = settings.MILVUS_USER,
        password: str = settings.MILVUS_PASSWORD,
        collection_name: str = settings.MILVUS_COLLECTION,
        dimension: int = settings.MILVUS_DIMENSION,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.collection_name = collection_name
        self.dimension = dimension
        self.uri = f"http://{host}:{port}"


class MilvusConnectionPool(ConnectionPool[MilvusClient]):
    """Milvus连接池实现"""
    
    def __init__(self, config: MilvusPoolConfig):
        self.milvus_config = config
        super().__init__(config)
    
    def _create_connection(self) -> MilvusClient:
        """创建新的Milvus客户端连接"""
        try:
            client = MilvusClient(
                host=self.milvus_config.host,
                port=self.milvus_config.port,
                user=self.milvus_config.user, 
                password=self.milvus_config.password,
                collection_name=self.milvus_config.collection_name,
                dimension=self.milvus_config.dimension
            )
            logger.debug(f"创建新的Milvus连接: {self.milvus_config.uri}")
            return client
        except Exception as e:
            logger.error(f"创建Milvus连接失败: {str(e)}")
            raise
    
    def _validate_connection(self, client: MilvusClient) -> bool:
        """验证Milvus连接是否有效"""
        try:
            # 简单的连接测试：检查集合是否可访问
            if client.collection is None:
                return False
                
            # 检查连接是否可以获取集合信息
            client.get_collection_stats()
            return True
        except Exception as e:
            logger.warning(f"Milvus连接验证失败: {str(e)}")
            return False
    
    def _close_connection(self, client: MilvusClient) -> None:
        """关闭Milvus连接"""
        try:
            client.close()
            logger.debug("Milvus连接已关闭")
        except Exception as e:
            logger.warning(f"关闭Milvus连接异常: {str(e)}")


class MilvusBatchInserter(BatchProcessor[MilvusClient]):
    """Milvus批量插入处理器"""
    
    def _process_batch(self, client: MilvusClient, batch_items: List[Dict[str, Any]]) -> List[str]:
        """批量插入数据到Milvus
        
        Args:
            client: Milvus客户端
            batch_items: 待插入数据项列表，每项包含 doc_id, chunk_id, text, vector, metadata
            
        Returns:
            成功插入的文档ID列表
        """
        try:
            # 验证连接并确保集合已创建
            if client.collection is None:
                client.create_collection(force_recreate=False)
                
            # 执行批量插入
            inserted_count = client.batch_insert(batch_items, batch_size=len(batch_items))
            
            # 返回成功插入的文档ID列表
            return [item.get("doc_id") for item in batch_items]
        except Exception as e:
            logger.error(f"批量插入失败: {str(e)}")
            raise


class MilvusBatchDeleter(BatchProcessor[MilvusClient]):
    """Milvus批量删除处理器"""
    
    def _process_batch(self, client: MilvusClient, batch_items: List[str]) -> Dict[str, bool]:
        """批量删除Milvus数据
        
        Args:
            client: Milvus客户端
            batch_items: 待删除的文档ID列表
            
        Returns:
            文档ID与删除结果的映射字典
        """
        try:
            # 验证连接并确保集合已加载
            if client.collection is None:
                client.create_collection(force_recreate=False)
                
            # 执行批量删除
            deleted_count = client.batch_delete_by_doc_ids(batch_items)
            
            # 返回删除结果
            results = {doc_id: True for doc_id in batch_items}
            return results
        except Exception as e:
            logger.error(f"批量删除失败: {str(e)}")
            raise


class MilvusBatchUpdater(BatchProcessor[MilvusClient]):
    """Milvus批量更新处理器"""
    
    def _process_batch(self, client: MilvusClient, batch_items: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, bool]:
        """批量更新Milvus数据
        
        Args:
            client: Milvus客户端
            batch_items: 待更新数据元组列表，每个元组包含 (doc_id, updated_data)
            
        Returns:
            文档ID与更新结果的映射字典
        """
        try:
            # 验证连接并确保集合已加载
            if client.collection is None:
                client.create_collection(force_recreate=False)
                
            # 准备更新数据
            results = {}
            for doc_id, data in batch_items:
                try:
                    # 先删除旧数据
                    client.delete_by_doc_id(doc_id)
                    
                    # 插入新数据
                    client.insert(
                        doc_id=data.get("doc_id", doc_id),
                        chunk_id=data.get("chunk_id", ""),
                        text=data.get("text", ""),
                        vector=data.get("vector", []),
                        metadata=data.get("metadata", {})
                    )
                    
                    results[doc_id] = True
                except Exception as e:
                    logger.error(f"更新文档 {doc_id} 失败: {str(e)}")
                    results[doc_id] = False
            
            return results
        except Exception as e:
            logger.error(f"批量更新失败: {str(e)}")
            raise


# 全局单例
_milvus_pool = None
_milvus_inserter = None
_milvus_deleter = None
_milvus_updater = None


def get_milvus_pool() -> MilvusConnectionPool:
    """获取Milvus连接池单例"""
    global _milvus_pool
    if _milvus_pool is None:
        config = MilvusPoolConfig(
            max_connections=settings.MILVUS_MAX_CONNECTIONS 
                if hasattr(settings, 'MILVUS_MAX_CONNECTIONS') else 10,
            min_connections=settings.MILVUS_MIN_CONNECTIONS 
                if hasattr(settings, 'MILVUS_MIN_CONNECTIONS') else 2
        )
        _milvus_pool = MilvusConnectionPool(config)
    return _milvus_pool


def get_milvus_batch_inserter() -> MilvusBatchInserter:
    """获取Milvus批量插入器单例"""
    global _milvus_inserter
    if _milvus_inserter is None:
        pool = get_milvus_pool()
        batch_size = settings.MILVUS_BATCH_SIZE if hasattr(settings, 'MILVUS_BATCH_SIZE') else 100
        _milvus_inserter = MilvusBatchInserter(pool, batch_size=batch_size)
    return _milvus_inserter


def get_milvus_batch_deleter() -> MilvusBatchDeleter:
    """获取Milvus批量删除器单例"""
    global _milvus_deleter
    if _milvus_deleter is None:
        pool = get_milvus_pool()
        batch_size = settings.MILVUS_BATCH_SIZE if hasattr(settings, 'MILVUS_BATCH_SIZE') else 100
        _milvus_deleter = MilvusBatchDeleter(pool, batch_size=batch_size)
    return _milvus_deleter


def get_milvus_batch_updater() -> MilvusBatchUpdater:
    """获取Milvus批量更新器单例"""
    global _milvus_updater
    if _milvus_updater is None:
        pool = get_milvus_pool()
        batch_size = settings.MILVUS_BATCH_SIZE if hasattr(settings, 'MILVUS_BATCH_SIZE') else 100
        _milvus_updater = MilvusBatchUpdater(pool, batch_size=batch_size)
    return _milvus_updater
