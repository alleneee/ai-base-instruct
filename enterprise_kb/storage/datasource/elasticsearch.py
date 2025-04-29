"""Elasticsearch向量数据库数据源实现"""
import logging
from typing import Any, Dict, List, Optional, Type, ClassVar, Tuple, Union
from pydantic import Field
import asyncio
import json

from llama_index.core.schema import TextNode, NodeWithScore, BaseNode

from enterprise_kb.storage.datasource.base import DataSource, DataSourceConfig
from enterprise_kb.storage.datasource.registry import register_datasource
from enterprise_kb.core.config.settings import settings
from enterprise_kb.storage.vector_store.elasticsearch_store import ElasticsearchVectorStore
from enterprise_kb.storage.pool.elasticsearch_pool import (
    get_elasticsearch_pool, get_elasticsearch_batch_inserter, 
    get_elasticsearch_batch_deleter, get_elasticsearch_batch_updater
)

logger = logging.getLogger(__name__)


class ElasticsearchDataSourceConfig(DataSourceConfig):
    """Elasticsearch数据源配置"""
    
    hosts: List[str] = Field(default_factory=lambda: [settings.ELASTICSEARCH_URL], description="Elasticsearch服务器地址")
    username: Optional[str] = Field(settings.ELASTICSEARCH_USERNAME, description="用户名")
    password: Optional[str] = Field(settings.ELASTICSEARCH_PASSWORD, description="密码")
    api_key: Optional[str] = Field(settings.ELASTICSEARCH_API_KEY, description="API密钥")
    collection_name: str = Field(settings.ELASTICSEARCH_COLLECTION, description="集合名称")
    dimension: int = Field(settings.ELASTICSEARCH_DIMENSION, description="向量维度")
    index_prefix: str = Field(settings.ELASTICSEARCH_INDEX_PREFIX if hasattr(settings, 'ELASTICSEARCH_INDEX_PREFIX') else "vector_", description="索引前缀")


@register_datasource("elasticsearch")
class ElasticsearchDataSource(DataSource[ElasticsearchDataSourceConfig]):
    """Elasticsearch向量数据库数据源"""
    
    _config_class: ClassVar[Type[ElasticsearchDataSourceConfig]] = ElasticsearchDataSourceConfig
    
    def __init__(self, config: ElasticsearchDataSourceConfig):
        """初始化Elasticsearch数据源
        
        Args:
            config: Elasticsearch数据源配置
        """
        super().__init__(config)
        self._client = None
        self.vector_store = None
        self._connected = False  # 连接状态标志
        self._connection_pool = get_elasticsearch_pool()  # 获取连接池
        self._batch_inserter = get_elasticsearch_batch_inserter()  # 批量插入器
        self._batch_deleter = get_elasticsearch_batch_deleter()  # 批量删除器
        self._batch_updater = get_elasticsearch_batch_updater()  # 批量更新器
    
    @classmethod
    def get_config_class(cls) -> Type[ElasticsearchDataSourceConfig]:
        """获取配置类"""
        return cls._config_class
    
    def _initialize(self) -> None:
        """初始化Elasticsearch向量存储
        
        注意：现在已经不在这里创建客户端，而是在connect()方法中从连接池获取
        """
        try:
            # 初始化向量存储
            self.vector_store = ElasticsearchVectorStore(
                hosts=self.config.hosts,
                username=self.config.username,
                password=self.config.password,
                api_key=self.config.api_key,
                index_prefix=self.config.index_prefix
            )
            
            # 通过传入现有客户端来初始化ES向量存储
            if self._client:
                self.vector_store.client = self._client
                self.vector_store._initialized = True
                
            # 确保集合存在
            loop = asyncio.get_event_loop()
            collection_exists = loop.run_until_complete(
                self.vector_store.has_collection(self.config.collection_name)
            )
            
            if not collection_exists:
                # 创建集合
                loop.run_until_complete(
                    self.vector_store.create_collection(
                        self.config.collection_name, 
                        self.config.dimension
                    )
                )
                logger.info(f"已创建Elasticsearch集合: {self.config.collection_name}")
            
            logger.info(f"成功初始化Elasticsearch向量存储: {self.config.hosts}")
        except Exception as e:
            logger.error(f"初始化Elasticsearch数据源失败: {str(e)}")
            raise ValueError(f"初始化Elasticsearch数据源失败: {str(e)}")
    
    async def connect(self) -> None:
        """连接到Elasticsearch服务器
        
        使用连接池获取连接，而不是每次都创建新连接
        """
        if not self._client or not self._connected:
            try:
                # 从连接池获取客户端而不是每次都创建新的
                loop = asyncio.get_event_loop()
                self._client = await loop.run_in_executor(None, self._connection_pool.get_connection)
                
                # 初始化向量存储
                self._initialize()
                self._connected = True
                logger.info(f"已连接到Elasticsearch服务器: {self.config.hosts}")
            except Exception as e:
                logger.error(f"连接到Elasticsearch服务器失败: {str(e)}")
                raise ValueError(f"连接到Elasticsearch服务器失败: {str(e)}")
    
    async def disconnect(self) -> None:
        """断开与Elasticsearch服务器的连接
        
        将连接放回连接池而不是关闭它
        """
        if self._client and self._connected:
            try:
                # 将客户端归还连接池，而不是关闭
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self._connection_pool.release_connection, self._client)
                except Exception as e:
                    logger.warning(f"归还Elasticsearch连接异常: {str(e)}")
                
                self._client = None
                self.vector_store = None
                self._connected = False
                logger.info("已断开与Elasticsearch服务器的连接")
            except Exception as e:
                logger.error(f"断开与Elasticsearch服务器的连接失败: {str(e)}")
    
    async def add_documents(self, nodes: List[BaseNode]) -> List[str]:
        """添加文档到Elasticsearch
        
        Args:
            nodes: 文档节点列表
            
        Returns:
            添加成功的节点ID列表
            
        Raises:
            ValueError: 添加失败
        """
        if not self._client:
            await self.connect()
            
        if not nodes:
            return []
            
        try:
            # 准备单次批量插入数据
            batch_data = []
            for node in nodes:
                # 获取向量
                embedding = node.embedding
                if embedding is None:
                    logger.warning(f"节点 {node.id_} 没有向量，跳过")
                    continue
                    
                # 构建数据项
                data_item = {
                    "collection_name": self.config.collection_name,
                    "id": node.id_,
                    "text": node.text,
                    "vector": embedding,
                    "metadata": node.metadata or {}
                }
                batch_data.append(data_item)
            
            # 使用批处理器添加文档
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._batch_inserter.add_batch, batch_data)
            
            # 强制刷新以立即执行
            results = await self._batch_inserter.async_flush()
            
            logger.info(f"成功添加 {len(results)} 个文档到Elasticsearch")
            return results
        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            raise ValueError(f"添加文档失败: {str(e)}")
    
    async def batch_add_documents(self, nodes: List[BaseNode], batch_size: int = 100) -> List[str]:
        """批量添加文档到Elasticsearch，使用批处理器提高性能
        
        Args:
            nodes: 文档节点列表
            batch_size: 批量大小
            
        Returns:
            添加成功的节点ID列表
            
        Raises:
            ValueError: 添加失败
        """
        if not nodes:
            return []
            
        try:
            # 准备批量数据
            batch_data = []
            for node in nodes:
                # 获取向量
                embedding = node.embedding
                if embedding is None:
                    logger.warning(f"节点 {node.id_} 没有向量，跳过")
                    continue
                    
                # 构建数据项
                data_item = {
                    "collection_name": self.config.collection_name,
                    "id": node.id_,
                    "text": node.text,
                    "vector": embedding,
                    "metadata": node.metadata or {}
                }
                batch_data.append(data_item)
            
            # 使用批处理器添加文档
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._batch_inserter.add_batch, batch_data)
            
            # 等待所有数据处理完成
            await self._batch_inserter.async_flush()
            
            # 返回添加成功的节点ID列表
            result_ids = [item["id"] for item in batch_data]
            logger.info(f"批量添加文档完成，共添加 {len(result_ids)} 个文档")
            return result_ids
        except Exception as e:
            logger.error(f"批量添加文档失败: {str(e)}")
            raise ValueError(f"批量添加文档失败: {str(e)}")
    
    async def update_document(self, doc_id: str, node: BaseNode) -> bool:
        """更新文档 (通过删除再插入实现)
        
        Args:
            doc_id: 文档ID
            node: 新的文档节点，必须包含embedding
            
        Returns:
            是否成功
            
        Raises:
            ValueError: 更新失败
        """
        if not self._client:
            await self.connect()
            
        try:
            # 获取向量
            embedding = node.embedding
            if embedding is None:
                raise ValueError(f"节点 {node.id_} 没有向量，无法更新")
                
            # 构建数据项
            old_data = {
                "collection_name": self.config.collection_name,
                "id": doc_id
            }
            
            new_data = {
                "collection_name": self.config.collection_name,
                "id": node.id_,
                "text": node.text,
                "vector": embedding,
                "metadata": node.metadata or {}
            }
            
            # 使用批处理器更新文档
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._batch_updater.add, (old_data, new_data))
            
            # 强制刷新以立即执行
            results = await self._batch_updater.async_flush()
            
            # 检查结果
            success = results.get(doc_id, False) if results else False
            
            if success:
                logger.info(f"成功更新文档 {doc_id}")
            else:
                logger.warning(f"文档 {doc_id} 更新失败或不存在")
                
            return success
        except Exception as e:
            logger.error(f"更新文档失败 (doc_id: {doc_id}): {str(e)}")
            raise ValueError(f"更新文档失败 (doc_id: {doc_id}): {str(e)}")
    
    async def batch_update_documents(self, updates: List[Tuple[str, BaseNode]], batch_size: int = 100) -> Dict[str, bool]:
        """批量更新文档，使用批处理器提高性能

        Args:
            updates: 元组列表，每个元组包含 (doc_id, new_node).
                     new_node 必须包含 embedding.
            batch_size: 批量大小

        Returns:
            文档ID及其更新结果的字典

        Raises:
            ValueError: 更新失败或数据源未连接.
        """
        if not updates:
            return {}
        
        try:
            # 准备批量更新数据
            batch_data = []
            for doc_id, node in updates:
                # 获取向量
                embedding = node.embedding
                if embedding is None:
                    logger.warning(f"节点 {node.id_} 没有向量，跳过")
                    continue
                    
                # 构建数据项
                old_data = {
                    "collection_name": self.config.collection_name,
                    "id": doc_id
                }
                
                new_data = {
                    "collection_name": self.config.collection_name,
                    "id": node.id_,
                    "text": node.text,
                    "vector": embedding,
                    "metadata": node.metadata or {}
                }
                
                batch_data.append((old_data, new_data))
            
            # 使用批处理器更新文档
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._batch_updater.add_batch, batch_data)
            
            # 等待所有数据处理完成
            results = await self._batch_updater.async_flush()
            
            # 如果结果为空，创建默认结果
            if not results:
                results = {doc_id: True for doc_id, _ in updates}
                
            success_count = sum(1 for success in results.values() if success)
            logger.info(f"批量更新文档完成，共成功更新 {success_count}/{len(updates)} 个文档")
            return results
        except Exception as e:
            logger.error(f"批量更新文档失败: {str(e)}")
            raise ValueError(f"批量更新文档失败: {str(e)}")
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功
            
        Raises:
            ValueError: 删除失败
        """
        if not doc_id:
            return False
            
        try:
            # 构建数据项
            data_item = {
                "collection_name": self.config.collection_name,
                "id": doc_id
            }
            
            # 使用批处理器删除单个文档
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._batch_deleter.add, data_item)
            
            # 强制立即刷新处理
            results = await self._batch_deleter.async_flush()
            
            # 解析结果
            success = results.get(doc_id, True) if results else True
            
            if success:
                logger.info(f"成功删除文档 {doc_id}")
            else:
                logger.warning(f"文档 {doc_id} 删除失败或不存在")
                
            return success
        except Exception as e:
            logger.error(f"删除文档失败 (doc_id: {doc_id}): {str(e)}")
            raise ValueError(f"删除文档失败 (doc_id: {doc_id}): {str(e)}")
    
    async def batch_delete_documents(self, doc_ids: List[str]) -> Dict[str, bool]:
        """批量删除文档，使用批处理器提高性能
        
        Args:
            doc_ids: 文档ID列表
            
        Returns:
            文档ID及其删除结果的字典
            
        Raises:
            ValueError: 删除失败
        """
        if not doc_ids:
            return {}
            
        try:
            # 准备批量删除数据
            batch_data = []
            for doc_id in doc_ids:
                data_item = {
                    "collection_name": self.config.collection_name,
                    "id": doc_id
                }
                batch_data.append(data_item)
            
            # 使用批处理器删除文档
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._batch_deleter.add_batch, batch_data)
            
            # 等待所有数据处理完成
            results = await self._batch_deleter.async_flush()
            
            # 如果结果为空，创建默认结果
            if not results:
                results = {doc_id: True for doc_id in doc_ids}
                
            logger.info(f"批量删除文档完成，共删除 {len(doc_ids)} 个文档")
            return results
        except Exception as e:
            logger.error(f"批量删除文档失败: {str(e)}")
            # 所有项都标记为失败
            return {doc_id: False for doc_id in doc_ids}
    
    async def search_documents(self, query_vector: List[float], top_k: int = 5, filter_expr: Optional[str] = None) -> List[NodeWithScore]:
        """执行向量相似度搜索

        Args:
            query_vector: 查询向量.
            top_k: 返回的最大结果数.
            filter_expr: Elasticsearch的过滤表达式 (ES查询JSON字符串).
            
        Returns:
            匹配节点的列表.
            
        Raises:
            ValueError: 搜索失败.
        """
        if not self._client:
            await self.connect()
                
        try:
            # 验证向量维度
            if len(query_vector) != self.config.dimension:
                raise ValueError(f"查询向量维度不匹配: 预期 {self.config.dimension}, 实际 {len(query_vector)}")
                
            # 确保向量存储已初始化
            if not self.vector_store:
                self._initialize()
                
            # 执行搜索
            results = await self.vector_store.search(
                collection_name=self.config.collection_name,
                query_vector=query_vector,
                limit=top_k,
                filter_expr=filter_expr
            )
            
            # 转换为NodeWithScore格式
            nodes_with_score = []
            for result in results:
                # 创建文本节点
                node = TextNode(
                    id_=result["id"],
                    text=result.get("text", ""),
                    metadata=result.get("metadata", {})
                )
                
                # 添加到结果列表
                nodes_with_score.append(NodeWithScore(
                    node=node,
                    score=result.get("score", 0.0)
                ))
            
            return nodes_with_score
        except Exception as e:
            logger.error(f"执行向量搜索失败: {str(e)}")
            raise ValueError(f"执行向量搜索失败: {str(e)}")
    
    async def count_documents(self, filter_expr: Optional[str] = None) -> int:
        """计算集合中的文档数量
        
        Args:
            filter_expr: 过滤表达式
            
        Returns:
            文档数量
        """
        if not self._client:
            await self.connect()
                
        try:
            count = await self.vector_store.count(
                collection_name=self.config.collection_name,
                filter_expr=filter_expr
            )
            return count
        except Exception as e:
            logger.error(f"计算文档数量失败: {str(e)}")
            return 0
    
    async def get_documents(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """获取指定ID的文档
        
        Args:
            doc_ids: 文档ID列表
            
        Returns:
            文档数据列表
        """
        if not self._client:
            await self.connect()
                
        try:
            docs = await self.vector_store.get(
                collection_name=self.config.collection_name,
                ids=doc_ids
            )
            return docs
        except Exception as e:
            logger.error(f"获取文档失败: {str(e)}")
            return []
    
    async def clear_collection(self) -> bool:
        """清空集合
        
        Returns:
            是否成功
        """
        if not self._client:
            await self.connect()
                
        try:
            # 删除并重建集合
            await self.vector_store.drop_collection(self.config.collection_name)
            await self.vector_store.create_collection(
                self.config.collection_name, 
                self.config.dimension
            )
            
            logger.info(f"成功清空集合 {self.config.collection_name}")
            return True
        except Exception as e:
            logger.error(f"清空集合失败: {str(e)}")
            return False
    
    async def health_check(self) -> bool:
        """检查Elasticsearch数据源健康状态，使用连接池进行检查
        
        Returns:
            是否健康
        """
        try:
            # 先检查连接池状态
            pool_health = self._connection_pool.health_check()
            if pool_health["active_connections"] == 0 and pool_health["available_connections"] == 0:
                logger.warning("Elasticsearch连接池健康检查失败: 无可用连接")
                return False
                
            # 尝试获取连接并进行检查
            if not self._client:
                # 尝试连接
                await self.connect()
                if not self._client:
                    return False
                    
            # 验证向量存储可用
            if not self.vector_store or not self.vector_store._initialized:
                self._initialize()
                
            # 检查集合是否存在
            collection_exists = await self.vector_store.has_collection(self.config.collection_name)
            if not collection_exists:
                logger.warning(f"集合 {self.config.collection_name} 不存在")
                return False
                
            # 通过所有检查
            return True
        except Exception as e:
            logger.error(f"Elasticsearch健康检查异常: {str(e)}")
            return False
    
    async def get_info(self) -> Dict[str, Any]:
        """获取数据源信息
        
        Returns:
            数据源信息字典
        """
        try:
            if not self._client:
                await self.connect()
                
            # 获取集合信息
            collections = await self.vector_store.list_collections()
            
            # 获取当前集合的文档数量
            doc_count = await self.count_documents()
                
            info = {
                "type": "elasticsearch",
                "hosts": self.config.hosts,
                "collection": self.config.collection_name,
                "dimension": self.config.dimension,
                "is_connected": self._client is not None and self._connected,
                "collections": collections,
                "documents_count": doc_count,
                "connection_pool": self._connection_pool.stats()
            }
            
            return info
        except Exception as e:
            logger.error(f"获取Elasticsearch信息失败: {str(e)}")
            return {
                "type": "elasticsearch", 
                "error": str(e),
                "is_connected": False
            }
