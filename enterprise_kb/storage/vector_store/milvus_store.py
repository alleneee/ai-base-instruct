"""
Milvus向量数据库实现
实现基于Milvus的向量存储
"""
import asyncio
import uuid
from typing import Dict, List, Optional, Any, Union
import logging

from pymilvus import (
    connections, 
    utility,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType
)

from enterprise_kb.storage.vector_store.base import VectorStoreBase
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

class MilvusVectorStore(VectorStoreBase):
    """
    Milvus向量数据库实现
    """
    
    def __init__(self, 
                 host: str = None, 
                 port: str = None,
                 user: str = None,
                 password: str = None,
                 timeout: int = 10):
        """
        初始化Milvus连接参数
        
        Args:
            host: Milvus服务器地址
            port: Milvus服务器端口
            user: 用户名（如果启用了认证）
            password: 密码（如果启用了认证）
            timeout: 连接超时时间（秒）
        """
        self.host = host or settings.MILVUS_HOST
        self.port = port or settings.MILVUS_PORT
        self.user = user or settings.MILVUS_USER
        self.password = password or settings.MILVUS_PASSWORD
        self.timeout = timeout
        self.connection_alias = "default"
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化Milvus连接"""
        if self._initialized:
            return
            
        # 使用asyncio运行阻塞操作
        await asyncio.to_thread(
            connections.connect, 
            alias=self.connection_alias,
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            timeout=self.timeout
        )
        self._initialized = True
        logger.info(f"成功连接到Milvus服务器: {self.host}:{self.port}")
    
    async def create_collection(self, collection_name: str, dimension: int, 
                              metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        创建新的向量集合
        
        Args:
            collection_name: 集合名称
            dimension: 向量维度
            metadata: 集合元数据
            
        Returns:
            bool: 创建是否成功
        """
        await self.initialize()
        
        if await self.has_collection(collection_name):
            logger.warning(f"集合 {collection_name} 已存在，无需创建")
            return True
            
        # 定义集合字段
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=36),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.JSON)
        ]
        
        # 创建集合schema
        schema = CollectionSchema(fields=fields, description=metadata.get("description", "") if metadata else "")
        
        # 创建集合
        try:
            # 使用asyncio运行阻塞操作
            await asyncio.to_thread(Collection, name=collection_name, schema=schema)
            
            # 为向量字段创建索引
            collection = await asyncio.to_thread(Collection, name=collection_name)
            index_params = {
                "metric_type": "L2",
                "index_type": "HNSW",
                "params": {"M": 8, "efConstruction": 64}
            }
            await asyncio.to_thread(
                collection.create_index, 
                field_name="vector", 
                index_params=index_params
            )
            
            # 加载集合到内存
            await asyncio.to_thread(collection.load)
            
            logger.info(f"成功创建集合: {collection_name}, 维度: {dimension}")
            return True
        except Exception as e:
            logger.error(f"创建集合失败: {str(e)}")
            return False
    
    async def drop_collection(self, collection_name: str) -> bool:
        """
        删除向量集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 删除是否成功
        """
        await self.initialize()
        
        if not await self.has_collection(collection_name):
            logger.warning(f"集合 {collection_name} 不存在，无需删除")
            return True
            
        try:
            # 使用asyncio运行阻塞操作
            await asyncio.to_thread(utility.drop_collection, collection_name=collection_name)
            logger.info(f"成功删除集合: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"删除集合失败: {str(e)}")
            return False
    
    async def has_collection(self, collection_name: str) -> bool:
        """
        检查集合是否存在
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 集合是否存在
        """
        await self.initialize()
        
        try:
            # 使用asyncio运行阻塞操作
            return await asyncio.to_thread(utility.has_collection, collection_name=collection_name)
        except Exception as e:
            logger.error(f"检查集合存在失败: {str(e)}")
            return False
    
    async def list_collections(self) -> List[str]:
        """
        列出所有集合名称
        
        Returns:
            List[str]: 集合名称列表
        """
        await self.initialize()
        
        try:
            # 使用asyncio运行阻塞操作
            return await asyncio.to_thread(utility.list_collections)
        except Exception as e:
            logger.error(f"列出集合失败: {str(e)}")
            return []
    
    async def insert(self, collection_name: str, vectors: List[List[float]], 
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
        await self.initialize()
        
        # 确保集合存在
        if not await self.has_collection(collection_name):
            logger.error(f"集合 {collection_name} 不存在，插入失败")
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
            
        # 准备文本列表（从元数据中提取）
        texts = [meta.get("text", "") for meta in metadata]
            
        try:
            # 获取集合对象
            collection = await asyncio.to_thread(Collection, name=collection_name)
            
            # 准备插入数据
            data = [
                ids,              # id
                vectors,          # vector
                texts,            # text
                metadata          # metadata
            ]
            
            # 插入数据
            await asyncio.to_thread(collection.insert, data=data)
            
            # 刷新数据确保可查询
            await asyncio.to_thread(collection.flush)
            
            logger.info(f"成功向集合 {collection_name} 插入 {len(vectors)} 条向量数据")
            return ids
        except Exception as e:
            logger.error(f"插入向量失败: {str(e)}")
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
            filter_expr: 过滤表达式
            
        Returns:
            List[Dict[str, Any]]: 搜索结果，包含id、score和metadata
        """
        await self.initialize()
        
        # 确保集合存在
        if not await self.has_collection(collection_name):
            logger.error(f"集合 {collection_name} 不存在，搜索失败")
            return []
            
        try:
            # 获取集合对象
            collection = await asyncio.to_thread(Collection, name=collection_name)
            
            # 确保集合已加载
            if not await asyncio.to_thread(collection.is_loaded):
                await asyncio.to_thread(collection.load)
            
            # 设置搜索参数
            search_params = {
                "metric_type": "L2",
                "params": {"ef": 64}
            }
            
            # 执行搜索
            results = await asyncio.to_thread(
                collection.search,
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=limit,
                expr=filter_expr,
                output_fields=["metadata", "text"]
            )
            
            # 处理搜索结果
            search_results = []
            for hits in results:  # 只有一个查询，所以只有一组结果
                for hit in hits:
                    result = {
                        "id": hit.id,
                        "score": hit.score,
                        "metadata": hit.entity.get("metadata", {}),
                        "text": hit.entity.get("text", "")
                    }
                    search_results.append(result)
            
            logger.info(f"在集合 {collection_name} 中搜索到 {len(search_results)} 条结果")
            return search_results
        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            return []
    
    async def delete(self, collection_name: str, ids: List[str]) -> bool:
        """
        删除指定ID的向量
        
        Args:
            collection_name: 集合名称
            ids: 要删除的向量ID列表
            
        Returns:
            bool: 删除是否成功
        """
        await self.initialize()
        
        # 确保集合存在
        if not await self.has_collection(collection_name):
            logger.error(f"集合 {collection_name} 不存在，删除失败")
            return False
            
        try:
            # 获取集合对象
            collection = await asyncio.to_thread(Collection, name=collection_name)
            
            # 构建删除表达式
            expr = f"id in {ids}"
            
            # 执行删除
            await asyncio.to_thread(collection.delete, expr=expr)
            
            logger.info(f"成功从集合 {collection_name} 中删除 {len(ids)} 条向量数据")
            return True
        except Exception as e:
            logger.error(f"删除向量失败: {str(e)}")
            return False
    
    async def count(self, collection_name: str, filter_expr: Optional[str] = None) -> int:
        """
        计算集合中的向量数量
        
        Args:
            collection_name: 集合名称
            filter_expr: 过滤表达式
            
        Returns:
            int: 向量数量
        """
        await self.initialize()
        
        # 确保集合存在
        if not await self.has_collection(collection_name):
            logger.error(f"集合 {collection_name} 不存在，计数失败")
            return 0
            
        try:
            # 获取集合对象
            collection = await asyncio.to_thread(Collection, name=collection_name)
            
            # 执行计数
            if filter_expr:
                count = await asyncio.to_thread(collection.query, expr=filter_expr, output_fields=["count(*)"])
                return len(count)
            else:
                return await asyncio.to_thread(collection.num_entities)
        except Exception as e:
            logger.error(f"计算向量数量失败: {str(e)}")
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
        
        # 确保集合存在
        if not await self.has_collection(collection_name):
            logger.error(f"集合 {collection_name} 不存在，获取失败")
            return []
            
        try:
            # 获取集合对象
            collection = await asyncio.to_thread(Collection, name=collection_name)
            
            # 构建查询表达式
            expr = f"id in {ids}"
            
            # 执行查询
            results = await asyncio.to_thread(
                collection.query,
                expr=expr,
                output_fields=["id", "vector", "metadata", "text"]
            )
            
            # 处理查询结果
            vectors = []
            for result in results:
                vector_data = {
                    "id": result["id"],
                    "vector": result["vector"],
                    "metadata": result["metadata"],
                    "text": result["text"]
                }
                vectors.append(vector_data)
            
            logger.info(f"成功从集合 {collection_name} 中获取 {len(vectors)} 条向量数据")
            return vectors
        except Exception as e:
            logger.error(f"获取向量失败: {str(e)}")
            return []
    
    async def close(self) -> None:
        """关闭Milvus连接"""
        if self._initialized:
            try:
                await asyncio.to_thread(connections.disconnect, alias=self.connection_alias)
                self._initialized = False
                logger.info("成功关闭Milvus连接")
            except Exception as e:
                logger.error(f"关闭Milvus连接失败: {str(e)}") 