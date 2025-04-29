"""
Elasticsearch向量数据库实现
实现基于Elasticsearch的向量存储，支持向量检索
"""
import asyncio
import uuid
import json
from typing import Dict, List, Optional, Any, Union
import logging

from elasticsearch import AsyncElasticsearch, NotFoundError

from enterprise_kb.storage.vector_store.base import VectorStoreBase
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

class ElasticsearchVectorStore(VectorStoreBase):
    """
    Elasticsearch向量数据库实现
    """
    
    def __init__(self, 
                 hosts: List[str] = None,
                 username: str = None,
                 password: str = None,
                 api_key: str = None,
                 index_prefix: str = "vector_",
                 timeout: int = 30):
        """
        初始化Elasticsearch连接参数
        
        Args:
            hosts: Elasticsearch服务器地址列表
            username: 用户名
            password: 密码
            api_key: API密钥（与用户名/密码二选一）
            index_prefix: 索引名称前缀
            timeout: 连接超时时间（秒）
        """
        self.hosts = hosts or [settings.ELASTICSEARCH_URL]
        self.username = username or settings.ELASTICSEARCH_USERNAME
        self.password = password or settings.ELASTICSEARCH_PASSWORD
        self.api_key = api_key or settings.ELASTICSEARCH_API_KEY
        self.index_prefix = index_prefix
        self.timeout = timeout
        self.client = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化Elasticsearch连接"""
        if self._initialized:
            return
            
        # 创建连接
        if self.api_key:
            self.client = AsyncElasticsearch(
                hosts=self.hosts,
                api_key=self.api_key,
                request_timeout=self.timeout
            )
        else:
            self.client = AsyncElasticsearch(
                hosts=self.hosts,
                basic_auth=(self.username, self.password) if self.username and self.password else None,
                request_timeout=self.timeout
            )
            
        # 检查连接
        try:
            info = await self.client.info()
            self._initialized = True
            logger.info(f"成功连接到Elasticsearch服务器: {info['version']['number']}")
        except Exception as e:
            logger.error(f"连接Elasticsearch失败: {str(e)}")
            raise
    
    def _get_index_name(self, collection_name: str) -> str:
        """获取完整的索引名称"""
        return f"{self.index_prefix}{collection_name}"
    
    async def create_collection(self, collection_name: str, dimension: int, 
                              metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        创建新的向量集合（在ES中为索引）
        
        Args:
            collection_name: 集合名称
            dimension: 向量维度
            metadata: 集合元数据
            
        Returns:
            bool: 创建是否成功
        """
        await self.initialize()
        
        index_name = self._get_index_name(collection_name)
        
        # 检查索引是否已存在
        if await self.has_collection(collection_name):
            logger.warning(f"索引 {index_name} 已存在，无需创建")
            return True
            
        # 创建索引映射
        index_settings = {
            "settings": {
                "number_of_shards": 3,
                "number_of_replicas": 1,
                "index.mapping.nested_objects.limit": 10000
            },
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "vector": {
                        "type": "dense_vector",
                        "dims": dimension,
                        "index": True,
                        "similarity": "cosine"  # 或 l2_norm, dot_product
                    },
                    "text": {"type": "text", "analyzer": "standard"},
                    "metadata": {"type": "object", "enabled": True}
                }
            }
        }
        
        # 添加集合描述到设置中
        if metadata:
            index_settings["settings"]["index.metadata"] = json.dumps(metadata)
        
        try:
            # 创建索引
            await self.client.indices.create(
                index=index_name,
                body=index_settings
            )
            
            logger.info(f"成功创建Elasticsearch索引: {index_name}, 维度: {dimension}")
            return True
        except Exception as e:
            logger.error(f"创建Elasticsearch索引失败: {str(e)}")
            return False
    
    async def drop_collection(self, collection_name: str) -> bool:
        """
        删除向量集合（在ES中为索引）
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 删除是否成功
        """
        await self.initialize()
        
        index_name = self._get_index_name(collection_name)
        
        # 检查索引是否存在
        if not await self.has_collection(collection_name):
            logger.warning(f"索引 {index_name} 不存在，无需删除")
            return True
            
        try:
            # 删除索引
            await self.client.indices.delete(index=index_name)
            
            logger.info(f"成功删除Elasticsearch索引: {index_name}")
            return True
        except Exception as e:
            logger.error(f"删除Elasticsearch索引失败: {str(e)}")
            return False
    
    async def has_collection(self, collection_name: str) -> bool:
        """
        检查集合是否存在（在ES中为索引）
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 集合是否存在
        """
        await self.initialize()
        
        index_name = self._get_index_name(collection_name)
        
        try:
            # 检查索引是否存在
            return await self.client.indices.exists(index=index_name)
        except Exception as e:
            logger.error(f"检查Elasticsearch索引存在失败: {str(e)}")
            return False
    
    async def list_collections(self) -> List[str]:
        """
        列出所有集合名称（在ES中为索引）
        
        Returns:
            List[str]: 集合名称列表
        """
        await self.initialize()
        
        try:
            # 获取所有索引
            response = await self.client.indices.get_alias(index=f"{self.index_prefix}*")
            
            # 提取集合名称（去除前缀）
            prefix_len = len(self.index_prefix)
            collections = [index_name[prefix_len:] for index_name in response]
            
            return collections
        except Exception as e:
            logger.error(f"列出Elasticsearch索引失败: {str(e)}")
            return []
    
    async def insert(self, collection_name: str, vectors: List[List[float]], 
                   ids: Optional[List[str]] = None,
                   metadata: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """
        向集合中插入向量（在ES中为索引文档）
        
        Args:
            collection_name: 集合名称
            vectors: 向量数据列表
            ids: 向量ID列表，如果不提供则自动生成
            metadata: 向量元数据列表
            
        Returns:
            List[str]: 插入的向量ID列表
        """
        await self.initialize()
        
        index_name = self._get_index_name(collection_name)
        
        # 确保索引存在
        if not await self.has_collection(collection_name):
            logger.error(f"索引 {index_name} 不存在，插入失败")
            return []
            
        # 准备ID列表
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
        elif len(ids) != len(vectors):
            logger.error("向量数量和ID数量不匹配")
            return []
        
        # 准备元数据列表
        if metadata is None:
            metadata = [{} for _ in range(len(vectors))]
        elif len(metadata) != len(vectors):
            logger.error("向量数量和元数据数量不匹配")
            return []
        
        # 批量操作请求
        bulk_operations = []
        
        for i, (vector_id, vector, meta) in enumerate(zip(ids, vectors, metadata)):
            # 从元数据中提取文本
            text = meta.get("text", "")
            
            # 准备文档
            doc = {
                "id": vector_id,
                "vector": vector,
                "text": text,
                "metadata": meta
            }
            
            # 添加到批量操作
            bulk_operations.append({"index": {"_index": index_name, "_id": vector_id}})
            bulk_operations.append(doc)
        
        try:
            # 执行批量操作
            response = await self.client.bulk(operations=bulk_operations, refresh=True)
            
            # 检查响应
            if response.get("errors", False):
                # 有错误发生
                failed_ids = []
                for item in response["items"]:
                    if "error" in item.get("index", {}):
                        failed_ids.append(item["index"]["_id"])
                logger.error(f"插入Elasticsearch文档部分失败，失败ID: {failed_ids}")
                # 返回成功的ID
                return [id for id in ids if id not in failed_ids]
            else:
                logger.info(f"成功向Elasticsearch索引 {index_name} 插入 {len(vectors)} 条向量数据")
                return ids
        except Exception as e:
            logger.error(f"插入Elasticsearch文档失败: {str(e)}")
            return []
    
    async def search(self, collection_name: str, query_vector: List[float], 
                   limit: int = 10, 
                   filter_expr: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        向量相似度搜索
        
        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            limit: 返回结果数量限制
            filter_expr: 过滤表达式 (ES查询JSON字符串)
            
        Returns:
            List[Dict[str, Any]]: 搜索结果，包含id、score和metadata
        """
        await self.initialize()
        
        index_name = self._get_index_name(collection_name)
        
        # 确保索引存在
        if not await self.has_collection(collection_name):
            logger.error(f"索引 {index_name} 不存在，搜索失败")
            return []
            
        # 构建向量查询
        query = {
            "knn": {
                "vector": {
                    "vector": query_vector,
                    "k": limit
                }
            }
        }
        
        # 如果有过滤表达式，添加过滤条件
        if filter_expr:
            try:
                filter_query = json.loads(filter_expr)
                query = {
                    "bool": {
                        "must": query,
                        "filter": filter_query
                    }
                }
            except json.JSONDecodeError:
                logger.error(f"过滤表达式格式错误: {filter_expr}")
                
        try:
            # 执行搜索
            response = await self.client.search(
                index=index_name,
                body={
                    "query": query,
                    "size": limit
                }
            )
            
            # 处理搜索结果
            search_results = []
            for hit in response["hits"]["hits"]:
                result = {
                    "id": hit["_source"]["id"],
                    "score": hit["_score"],
                    "metadata": hit["_source"]["metadata"],
                    "text": hit["_source"]["text"]
                }
                search_results.append(result)
            
            logger.info(f"在Elasticsearch索引 {index_name} 中搜索到 {len(search_results)} 条结果")
            return search_results
        except Exception as e:
            logger.error(f"Elasticsearch向量搜索失败: {str(e)}")
            return []
    
    async def delete(self, collection_name: str, ids: List[str]) -> bool:
        """
        删除指定ID的向量（在ES中为删除文档）
        
        Args:
            collection_name: 集合名称
            ids: 要删除的向量ID列表
            
        Returns:
            bool: 删除是否成功
        """
        await self.initialize()
        
        index_name = self._get_index_name(collection_name)
        
        # 确保索引存在
        if not await self.has_collection(collection_name):
            logger.error(f"索引 {index_name} 不存在，删除失败")
            return False
            
        # 构建批量删除操作
        bulk_operations = []
        for vector_id in ids:
            bulk_operations.append({"delete": {"_index": index_name, "_id": vector_id}})
        
        try:
            # 执行批量操作
            response = await self.client.bulk(operations=bulk_operations, refresh=True)
            
            # 检查响应
            if response.get("errors", False):
                # 有错误发生
                failed_ids = []
                for item in response["items"]:
                    if "error" in item.get("delete", {}):
                        failed_ids.append(item["delete"]["_id"])
                logger.error(f"删除Elasticsearch文档部分失败，失败ID: {failed_ids}")
                return len(failed_ids) < len(ids)  # 如果大部分成功则返回True
            else:
                logger.info(f"成功从Elasticsearch索引 {index_name} 中删除 {len(ids)} 条向量数据")
                return True
        except Exception as e:
            logger.error(f"删除Elasticsearch文档失败: {str(e)}")
            return False
    
    async def count(self, collection_name: str, filter_expr: Optional[str] = None) -> int:
        """
        计算集合中的向量数量
        
        Args:
            collection_name: 集合名称
            filter_expr: 过滤表达式 (ES查询JSON字符串)
            
        Returns:
            int: 向量数量
        """
        await self.initialize()
        
        index_name = self._get_index_name(collection_name)
        
        # 确保索引存在
        if not await self.has_collection(collection_name):
            logger.error(f"索引 {index_name} 不存在，计数失败")
            return 0
            
        # 构建查询
        body = {}
        if filter_expr:
            try:
                query = json.loads(filter_expr)
                body = {"query": query}
            except json.JSONDecodeError:
                logger.error(f"过滤表达式格式错误: {filter_expr}")
                
        try:
            # 执行计数
            response = await self.client.count(index=index_name, body=body if filter_expr else None)
            
            return response["count"]
        except Exception as e:
            logger.error(f"计算Elasticsearch文档数量失败: {str(e)}")
            return 0
    
    async def get(self, collection_name: str, ids: List[str]) -> List[Dict[str, Any]]:
        """
        获取指定ID的向量
        
        Args:
            collection_name: 集合名称
            ids: 向量ID列表
            
        Returns:
            List[Dict[str, Any]]: 向量数据列表，包含id、vector和metadata
        """
        await self.initialize()
        
        index_name = self._get_index_name(collection_name)
        
        # 确保索引存在
        if not await self.has_collection(collection_name):
            logger.error(f"索引 {index_name} 不存在，获取失败")
            return []
            
        try:
            # 执行多文档查询
            body = {"ids": ids}
            response = await self.client.mget(index=index_name, body=body)
            
            # 处理查询结果
            vectors = []
            for doc in response["docs"]:
                if doc.get("found", False):
                    vector_data = {
                        "id": doc["_source"]["id"],
                        "vector": doc["_source"]["vector"],
                        "metadata": doc["_source"]["metadata"],
                        "text": doc["_source"]["text"]
                    }
                    vectors.append(vector_data)
                else:
                    logger.warning(f"未找到ID为 {doc['_id']} 的文档")
            
            logger.info(f"成功从Elasticsearch索引 {index_name} 中获取 {len(vectors)} 条向量数据")
            return vectors
        except Exception as e:
            logger.error(f"获取Elasticsearch文档失败: {str(e)}")
            return []
    
    async def close(self) -> None:
        """关闭Elasticsearch连接"""
        if self._initialized and self.client:
            try:
                await self.client.close()
                self._initialized = False
                logger.info("成功关闭Elasticsearch连接")
            except Exception as e:
                logger.error(f"关闭Elasticsearch连接失败: {str(e)}") 