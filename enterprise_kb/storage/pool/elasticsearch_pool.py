"""
Elasticsearch连接池实现
提供高效的Elasticsearch连接池管理和批量操作功能
"""
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
import time
import json
import asyncio

from elasticsearch import AsyncElasticsearch, NotFoundError, TransportError

from enterprise_kb.storage.pool.base import ConnectionPool, BatchProcessor, PoolConfig
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)


class ElasticsearchPoolConfig(PoolConfig):
    """Elasticsearch连接池配置"""
    
    def __init__(
        self,
        hosts: List[str] = None,
        username: str = None,
        password: str = None,
        api_key: str = None,
        timeout: int = 30,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.hosts = hosts or [settings.ELASTICSEARCH_URL]
        self.username = username or settings.ELASTICSEARCH_USERNAME
        self.password = password or settings.ELASTICSEARCH_PASSWORD
        self.api_key = api_key or settings.ELASTICSEARCH_API_KEY
        self.timeout = timeout


class ElasticsearchConnectionPool(ConnectionPool[AsyncElasticsearch]):
    """Elasticsearch连接池实现"""
    
    def __init__(self, config: ElasticsearchPoolConfig):
        self.es_config = config
        super().__init__(config)
    
    def _create_connection(self) -> AsyncElasticsearch:
        """创建新的Elasticsearch客户端连接"""
        try:
            # 根据配置创建连接
            if self.es_config.api_key:
                client = AsyncElasticsearch(
                    hosts=self.es_config.hosts,
                    api_key=self.es_config.api_key,
                    request_timeout=self.es_config.timeout
                )
            else:
                client = AsyncElasticsearch(
                    hosts=self.es_config.hosts,
                    basic_auth=(self.es_config.username, self.es_config.password) 
                        if self.es_config.username and self.es_config.password else None,
                    request_timeout=self.es_config.timeout
                )
                
            logger.debug(f"创建新的Elasticsearch连接: {self.es_config.hosts}")
            return client
        except Exception as e:
            logger.error(f"创建Elasticsearch连接失败: {str(e)}")
            raise
    
    async def _validate_connection_async(self, client: AsyncElasticsearch) -> bool:
        """异步验证Elasticsearch连接是否有效"""
        try:
            # 检查连接状态
            info = await client.info()
            return True
        except Exception as e:
            logger.warning(f"Elasticsearch连接验证失败: {str(e)}")
            return False
    
    def _validate_connection(self, client: AsyncElasticsearch) -> bool:
        """验证Elasticsearch连接是否有效
        
        注意：这是一个同步方法，但ES客户端是异步的，
        因此我们需要创建一个事件循环来运行异步验证
        """
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._validate_connection_async(client))
            loop.close()
            return result
        except Exception as e:
            logger.warning(f"验证Elasticsearch连接失败: {str(e)}")
            return False
    
    async def _close_connection_async(self, client: AsyncElasticsearch) -> None:
        """异步关闭Elasticsearch连接"""
        try:
            await client.close()
            logger.debug("Elasticsearch连接已关闭")
        except Exception as e:
            logger.warning(f"关闭Elasticsearch连接异常: {str(e)}")
    
    def _close_connection(self, client: AsyncElasticsearch) -> None:
        """关闭Elasticsearch连接"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._close_connection_async(client))
            loop.close()
        except Exception as e:
            logger.warning(f"关闭Elasticsearch连接异常: {str(e)}")


class ElasticsearchBatchInserter(BatchProcessor[AsyncElasticsearch]):
    """Elasticsearch批量插入处理器"""
    
    def __init__(
        self, 
        connection_pool: ElasticsearchConnectionPool,
        index_prefix: str = "vector_",
        batch_size: int = 100,
        **kwargs
    ):
        super().__init__(connection_pool, batch_size=batch_size, **kwargs)
        self.index_prefix = index_prefix
    
    def _get_index_name(self, collection_name: str) -> str:
        """获取完整的索引名称"""
        return f"{self.index_prefix}{collection_name}"
    
    async def _process_batch_async(self, client: AsyncElasticsearch, batch_items: List[Dict[str, Any]]) -> List[str]:
        """异步批量插入数据到Elasticsearch
        
        Args:
            client: Elasticsearch客户端
            batch_items: 待插入数据项列表，每项包含 collection_name, id, vector, metadata, text
            
        Returns:
            成功插入的文档ID列表
        """
        if not batch_items:
            return []
            
        # 按索引分组
        grouped_items = {}
        for item in batch_items:
            collection_name = item.get("collection_name")
            if not collection_name:
                logger.warning(f"批量插入项缺少collection_name字段，跳过: {item}")
                continue
                
            index_name = self._get_index_name(collection_name)
            if index_name not in grouped_items:
                grouped_items[index_name] = []
            grouped_items[index_name].append(item)
        
        # 对每个索引执行批量操作
        inserted_ids = []
        for index_name, items in grouped_items.items():
            # 准备批量请求体
            bulk_data = []
            
            for item in items:
                doc_id = item.get("id")
                if not doc_id:
                    # 如果没有提供ID，生成一个
                    import uuid
                    doc_id = str(uuid.uuid4())
                    item["id"] = doc_id
                
                # 创建索引操作
                index_action = {
                    "index": {
                        "_index": index_name,
                        "_id": doc_id
                    }
                }
                
                # 文档内容
                doc = {
                    "id": doc_id,
                    "vector": item.get("vector", []),
                    "metadata": item.get("metadata", {}),
                    "text": item.get("text", "")
                }
                
                # 添加到批量操作
                bulk_data.append(index_action)
                bulk_data.append(doc)
            
            try:
                # 执行批量操作
                response = await client.bulk(operations=bulk_data, refresh=True)
                
                # 处理响应
                if response.get("errors", False):
                    # 部分操作可能失败
                    for item in response["items"]:
                        if "error" not in item.get("index", {}):
                            inserted_ids.append(item["index"]["_id"])
                        else:
                            logger.error(f"插入文档失败: {item['index']['error']}")
                else:
                    # 全部成功
                    inserted_ids.extend([item["id"] for item in items])
                    
                logger.info(f"批量插入 {len(items)} 条数据到索引 {index_name}，成功 {len(inserted_ids)} 条")
            except Exception as e:
                logger.error(f"批量插入到索引 {index_name} 失败: {str(e)}")
                # 不要抛出异常，让处理继续进行
        
        return inserted_ids
    
    def _process_batch(self, client: AsyncElasticsearch, batch_items: List[Dict[str, Any]]) -> List[str]:
        """批量插入数据到Elasticsearch"""
        # 创建一个新的事件循环来运行异步操作
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self._process_batch_async(client, batch_items))
            return result
        finally:
            loop.close()


class ElasticsearchBatchDeleter(BatchProcessor[AsyncElasticsearch]):
    """Elasticsearch批量删除处理器"""
    
    def __init__(
        self, 
        connection_pool: ElasticsearchConnectionPool,
        index_prefix: str = "vector_",
        batch_size: int = 100,
        **kwargs
    ):
        super().__init__(connection_pool, batch_size=batch_size, **kwargs)
        self.index_prefix = index_prefix
    
    def _get_index_name(self, collection_name: str) -> str:
        """获取完整的索引名称"""
        return f"{self.index_prefix}{collection_name}"
    
    async def _process_batch_async(self, client: AsyncElasticsearch, batch_items: List[Dict[str, Any]]) -> Dict[str, bool]:
        """异步批量删除Elasticsearch数据
        
        Args:
            client: Elasticsearch客户端
            batch_items: 待删除数据项列表，每项包含 collection_name, id
            
        Returns:
            文档ID与删除结果的映射字典
        """
        if not batch_items:
            return {}
            
        # 按索引分组
        grouped_items = {}
        for item in batch_items:
            collection_name = item.get("collection_name")
            doc_id = item.get("id")
            
            if not collection_name or not doc_id:
                logger.warning(f"批量删除项缺少必要字段，跳过: {item}")
                continue
                
            index_name = self._get_index_name(collection_name)
            if index_name not in grouped_items:
                grouped_items[index_name] = []
            grouped_items[index_name].append(doc_id)
        
        # 对每个索引执行批量删除
        results = {}
        for index_name, ids in grouped_items.items():
            # 准备批量请求体
            bulk_data = []
            
            for doc_id in ids:
                # 删除操作
                delete_action = {
                    "delete": {
                        "_index": index_name,
                        "_id": doc_id
                    }
                }
                
                # 添加到批量操作
                bulk_data.append(delete_action)
            
            try:
                # 执行批量操作
                response = await client.bulk(operations=bulk_data, refresh=True)
                
                # 处理响应
                if response.get("errors", False):
                    # 部分操作可能失败
                    for i, item in enumerate(response["items"]):
                        doc_id = ids[i]
                        if "error" not in item.get("delete", {}):
                            results[doc_id] = True
                        else:
                            results[doc_id] = False
                            logger.error(f"删除文档 {doc_id} 失败: {item['delete'].get('error')}")
                else:
                    # 全部成功
                    for doc_id in ids:
                        results[doc_id] = True
                    
                logger.info(f"批量删除 {len(ids)} 条数据从索引 {index_name}，成功 {sum(1 for v in results.values() if v)} 条")
            except Exception as e:
                logger.error(f"批量删除索引 {index_name} 失败: {str(e)}")
                # 所有项标记为失败
                for doc_id in ids:
                    results[doc_id] = False
        
        return results
    
    def _process_batch(self, client: AsyncElasticsearch, batch_items: List[Dict[str, Any]]) -> Dict[str, bool]:
        """批量删除Elasticsearch数据"""
        # 创建一个新的事件循环来运行异步操作
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self._process_batch_async(client, batch_items))
            return result
        finally:
            loop.close()


class ElasticsearchBatchUpdater(BatchProcessor[AsyncElasticsearch]):
    """Elasticsearch批量更新处理器"""
    
    def __init__(
        self, 
        connection_pool: ElasticsearchConnectionPool,
        index_prefix: str = "vector_",
        batch_size: int = 100,
        **kwargs
    ):
        super().__init__(connection_pool, batch_size=batch_size, **kwargs)
        self.index_prefix = index_prefix
    
    def _get_index_name(self, collection_name: str) -> str:
        """获取完整的索引名称"""
        return f"{self.index_prefix}{collection_name}"
    
    async def _process_batch_async(self, client: AsyncElasticsearch, batch_items: List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> Dict[str, bool]:
        """异步批量更新Elasticsearch数据
        
        Args:
            client: Elasticsearch客户端
            batch_items: 待更新数据项列表，每项为元组 (原始数据, 新数据)
            
        Returns:
            文档ID与更新结果的映射字典
        """
        if not batch_items:
            return {}
        
        # 按索引分组
        grouped_items = {}
        for old_data, new_data in batch_items:
            collection_name = old_data.get("collection_name") or new_data.get("collection_name")
            doc_id = old_data.get("id") or new_data.get("id")
            
            if not collection_name or not doc_id:
                logger.warning(f"批量更新项缺少必要字段，跳过: {old_data} -> {new_data}")
                continue
                
            index_name = self._get_index_name(collection_name)
            if index_name not in grouped_items:
                grouped_items[index_name] = []
            grouped_items[index_name].append((doc_id, new_data))
        
        # 对每个索引执行批量更新
        results = {}
        for index_name, items in grouped_items.items():
            # 准备批量请求体
            bulk_data = []
            
            for doc_id, new_data in items:
                # 更新操作（实际上是删除后插入）
                delete_action = {
                    "delete": {
                        "_index": index_name,
                        "_id": doc_id
                    }
                }
                
                index_action = {
                    "index": {
                        "_index": index_name,
                        "_id": doc_id
                    }
                }
                
                # 文档内容
                doc = {
                    "id": doc_id,
                    "vector": new_data.get("vector", []),
                    "metadata": new_data.get("metadata", {}),
                    "text": new_data.get("text", "")
                }
                
                # 添加到批量操作
                bulk_data.append(delete_action)
                bulk_data.append(index_action)
                bulk_data.append(doc)
            
            try:
                # 执行批量操作
                response = await client.bulk(operations=bulk_data, refresh=True)
                
                # 处理响应
                for i, (doc_id, _) in enumerate(items):
                    # 每个更新操作有两个响应项（删除和索引）
                    delete_idx = i * 2
                    index_idx = i * 2 + 1
                    
                    # 检查删除和索引操作是否都成功
                    delete_ok = "error" not in response["items"][delete_idx].get("delete", {})
                    index_ok = "error" not in response["items"][index_idx].get("index", {})
                    
                    results[doc_id] = delete_ok and index_ok
                    
                    if not results[doc_id]:
                        logger.error(f"更新文档 {doc_id} 失败")
                
                logger.info(f"批量更新 {len(items)} 条数据到索引 {index_name}，成功 {sum(1 for v in results.values() if v)} 条")
            except Exception as e:
                logger.error(f"批量更新索引 {index_name} 失败: {str(e)}")
                # 所有项标记为失败
                for doc_id, _ in items:
                    results[doc_id] = False
        
        return results
    
    def _process_batch(self, client: AsyncElasticsearch, batch_items: List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> Dict[str, bool]:
        """批量更新Elasticsearch数据"""
        # 创建一个新的事件循环来运行异步操作
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self._process_batch_async(client, batch_items))
            return result
        finally:
            loop.close()


# 全局单例
_elasticsearch_pool = None
_elasticsearch_inserter = None
_elasticsearch_deleter = None
_elasticsearch_updater = None


def get_elasticsearch_pool() -> ElasticsearchConnectionPool:
    """获取Elasticsearch连接池单例"""
    global _elasticsearch_pool
    if _elasticsearch_pool is None:
        config = ElasticsearchPoolConfig(
            max_connections=settings.ELASTICSEARCH_MAX_CONNECTIONS
                if hasattr(settings, 'ELASTICSEARCH_MAX_CONNECTIONS') else 10,
            min_connections=settings.ELASTICSEARCH_MIN_CONNECTIONS
                if hasattr(settings, 'ELASTICSEARCH_MIN_CONNECTIONS') else 2
        )
        _elasticsearch_pool = ElasticsearchConnectionPool(config)
    return _elasticsearch_pool


def get_elasticsearch_batch_inserter() -> ElasticsearchBatchInserter:
    """获取Elasticsearch批量插入器单例"""
    global _elasticsearch_inserter
    if _elasticsearch_inserter is None:
        pool = get_elasticsearch_pool()
        batch_size = settings.ELASTICSEARCH_BATCH_SIZE if hasattr(settings, 'ELASTICSEARCH_BATCH_SIZE') else 100
        _elasticsearch_inserter = ElasticsearchBatchInserter(
            pool, 
            batch_size=batch_size,
            index_prefix=settings.ELASTICSEARCH_INDEX_PREFIX if hasattr(settings, 'ELASTICSEARCH_INDEX_PREFIX') else "vector_"
        )
    return _elasticsearch_inserter


def get_elasticsearch_batch_deleter() -> ElasticsearchBatchDeleter:
    """获取Elasticsearch批量删除器单例"""
    global _elasticsearch_deleter
    if _elasticsearch_deleter is None:
        pool = get_elasticsearch_pool()
        batch_size = settings.ELASTICSEARCH_BATCH_SIZE if hasattr(settings, 'ELASTICSEARCH_BATCH_SIZE') else 100
        _elasticsearch_deleter = ElasticsearchBatchDeleter(
            pool, 
            batch_size=batch_size,
            index_prefix=settings.ELASTICSEARCH_INDEX_PREFIX if hasattr(settings, 'ELASTICSEARCH_INDEX_PREFIX') else "vector_"
        )
    return _elasticsearch_deleter


def get_elasticsearch_batch_updater() -> ElasticsearchBatchUpdater:
    """获取Elasticsearch批量更新器单例"""
    global _elasticsearch_updater
    if _elasticsearch_updater is None:
        pool = get_elasticsearch_pool()
        batch_size = settings.ELASTICSEARCH_BATCH_SIZE if hasattr(settings, 'ELASTICSEARCH_BATCH_SIZE') else 100
        _elasticsearch_updater = ElasticsearchBatchUpdater(
            pool, 
            batch_size=batch_size,
            index_prefix=settings.ELASTICSEARCH_INDEX_PREFIX if hasattr(settings, 'ELASTICSEARCH_INDEX_PREFIX') else "vector_"
        )
    return _elasticsearch_updater
