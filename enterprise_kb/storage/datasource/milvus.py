"""Milvus向量数据库数据源实现"""
import logging
from typing import Any, Dict, List, Optional, Type, ClassVar, Tuple, Union
from pydantic import Field
import asyncio
import json

from llama_index.core.schema import TextNode, NodeWithScore, BaseNode
from llama_index.vector_stores.milvus import MilvusVectorStore, IndexManagement
from pymilvus import Collection, utility, connections, RRFRanker

from enterprise_kb.storage.datasource.base import DataSource, DataSourceConfig
from enterprise_kb.storage.datasource.registry import register_datasource
from enterprise_kb.core.config.settings import settings
from enterprise_kb.utils.milvus_client import get_milvus_client, MilvusClient
from enterprise_kb.storage.pool.milvus_pool import (
    get_milvus_pool, get_milvus_batch_inserter, 
    get_milvus_batch_deleter, get_milvus_batch_updater
)

logger = logging.getLogger(__name__)


class MilvusDataSourceConfig(DataSourceConfig):
    """Milvus数据源配置"""
    
    uri: str = Field(settings.MILVUS_URI, description="Milvus服务器URI")
    user: str = Field(settings.MILVUS_USER, description="用户名")
    password: str = Field(settings.MILVUS_PASSWORD, description="密码")
    collection_name: str = Field(settings.MILVUS_COLLECTION, description="集合名称")
    dimension: int = Field(settings.MILVUS_DIMENSION, description="向量维度")
    text_field: str = Field(settings.MILVUS_TEXT_FIELD, description="文本字段名")
    embedding_field: str = Field(settings.MILVUS_EMBEDDING_FIELD, description="向量字段名")
    metadata_field: str = Field(settings.MILVUS_METADATA_FIELD, description="元数据字段名")
    id_field: str = Field(settings.MILVUS_ID_FIELD, description="ID字段名")


@register_datasource("milvus")
class MilvusDataSource(DataSource[MilvusDataSourceConfig]):
    """Milvus向量数据库数据源"""
    
    _config_class: ClassVar[Type[MilvusDataSourceConfig]] = MilvusDataSourceConfig
    
    def __init__(self, config: MilvusDataSourceConfig):
        """初始化Milvus数据源
        
        Args:
            config: Milvus数据源配置
        """
        super().__init__(config)
        self._client = None
        self.vector_store = None
        self.collection = None  # 添加集合对象引用
        self._connected = False  # 添加连接状态标志
        self._connection_pool = get_milvus_pool()  # 获取连接池
        self._batch_inserter = get_milvus_batch_inserter()  # 批量插入器
        self._batch_deleter = get_milvus_batch_deleter()  # 批量删除器
        self._batch_updater = get_milvus_batch_updater()  # 批量更新器
    
    @classmethod
    def get_config_class(cls) -> Type[MilvusDataSourceConfig]:
        """获取配置类"""
        return cls._config_class
    
    def _initialize(self) -> None:
        """初始化Milvus向量存储
        
        注意：现在已经不在这里创建客户端，而是在connect()方法中从连接池获取
        """
        try:
            # 初始化Milvus向量存储
            uri = self.config.uri
            
            # 确定索引管理策略
            index_management_str = settings.MILVUS_INDEX_MANAGEMENT
            index_management = IndexManagement.CREATE_IF_NOT_EXISTS
            if index_management_str == "NO_VALIDATION":
                index_management = IndexManagement.NO_VALIDATION
            
            # 创建向量存储实例
            self.vector_store = MilvusVectorStore(
                uri=uri,
                collection_name=self.config.collection_name,
                dim=self.config.dimension,
                text_field=self.config.text_field,
                embedding_field=self.config.embedding_field,
                metadata_field=self.config.metadata_field,
                id_field=self.config.id_field,
                index_management=index_management,
                overwrite=settings.MILVUS_OVERWRITE
            )
            
            # 如果集合存在，加载集合
            if self._client and utility.has_collection(self.config.collection_name):
                self.collection = Collection(self.config.collection_name)
            
            logger.info(f"成功初始化Milvus向量存储: {uri}")
        except Exception as e:
            logger.error(f"初始化Milvus数据源失败: {str(e)}")
            raise ValueError(f"初始化Milvus数据源失败: {str(e)}")
    
    async def connect(self) -> None:
        """连接到Milvus服务器
        
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
                logger.info(f"已连接到Milvus服务器: {self.config.uri}")
            except Exception as e:
                logger.error(f"连接到Milvus服务器失败: {str(e)}")
                raise ValueError(f"连接到Milvus服务器失败: {str(e)}")
    
    async def disconnect(self) -> None:
        """断开与Milvus服务器的连接
        
        将连接放回连接池而不是关闭它
        """
        if self._client and self._connected:
            try:
                # 释放集合资源
                if self.collection:
                    try:
                        self.collection.release()
                    except Exception as e:
                        logger.warning(f"释放集合资源异常: {str(e)}")
                    self.collection = None
                
                # 释放向量存储资源
                self.vector_store = None
                
                # 将客户端归还连接池，而不是关闭
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self._connection_pool.release_connection, self._client)
                except Exception as e:
                    logger.warning(f"归还Milvus连接异常: {str(e)}")
                
                self._client = None
                self._connected = False
                logger.info("已断开与Milvus服务器的连接")
            except Exception as e:
                logger.error(f"断开与Milvus服务器的连接失败: {str(e)}")
    
    async def add_documents(self, nodes: List[BaseNode]) -> List[str]:
        """添加文档到Milvus
        
        Args:
            nodes: 文档节点列表
            
        Returns:
            添加成功的节点ID列表
            
        Raises:
            ValueError: 添加失败
        """
        if not self.vector_store:
            await self.connect()
            if not self.vector_store:
                raise ValueError("Milvus数据源未连接")
            
        try:
            # 使用LlamaIndex的向量存储添加节点
            node_ids = self.vector_store.add(nodes)
            logger.info(f"成功添加 {len(nodes)} 个文档到Milvus")
            return node_ids
        except Exception as e:
            logger.error(f"添加文档到Milvus失败: {str(e)}")
            raise ValueError(f"添加文档失败: {str(e)}")
    
    async def batch_add_documents(self, nodes: List[BaseNode], batch_size: int = 100) -> List[str]:
        """批量添加文档到Milvus，使用批处理器提高性能
        
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
                    "doc_id": node.id_,
                    "chunk_id": getattr(node, "chunk_id", ""),
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
            result_ids = [item["doc_id"] for item in batch_data]
            logger.info(f"批量添加文档完成，共添加 {len(result_ids)} 个文档")
            return result_ids
        except Exception as e:
            logger.error(f"批量添加文档失败: {str(e)}")
            raise ValueError(f"批量添加文档失败: {str(e)}")
    
    async def update_document(self, doc_id: str, node: BaseNode) -> bool:
        """更新文档 (通过Upsert实现)

        利用Milvus在存在主键时insert操作的upsert特性。
        如果具有相同主键(doc_id)的记录存在，则更新；否则，插入。

        Args:
            doc_id: 文档ID (必须与Milvus集合的主键对应).
            node: 新的文档节点数据 (必须包含embedding).

        Returns:
            是否成功 (如果add操作没有抛出异常，则认为成功).

        Raises:
            ValueError: 更新失败或数据源未连接.
        """
        if not self.vector_store:
            await self.connect()
            if not self.vector_store:
                raise ValueError("Milvus数据源未连接")

        try:
            # 确保节点的ID被设置为doc_id (主键)
            node.id_ = doc_id
            # LlamaIndex 的 add 方法在Milvus集合有主键时通常会执行upsert操作
            self.vector_store.add([node])
            logger.info(f"成功 Upsert 文档 (doc_id): {doc_id}")
            return True
        except Exception as e:
            logger.exception(f"Upsert Milvus 文档失败 (doc_id: {doc_id}): {str(e)}")
            # Reraise as ValueError or a custom exception if needed
            raise ValueError(f"Upsert 文档失败 (doc_id: {doc_id}): {str(e)}")
    
    async def batch_update_documents(self, updates: List[Tuple[str, BaseNode]], batch_size: int = 100) -> Dict[str, bool]:
        """批量更新/插入文档，使用批处理器提高性能

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
                data_item = {
                    "doc_id": node.id_,
                    "chunk_id": getattr(node, "chunk_id", ""),
                    "text": node.text,
                    "vector": embedding,
                    "metadata": node.metadata or {}
                }
                batch_data.append((doc_id, data_item))
            
            # 使用批处理器更新文档
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._batch_updater.add_batch, batch_data)
            
            # 等待所有数据处理完成
            results = await self._batch_updater.async_flush()
            
            # 如果结果为空，创建默认结果
            if not results:
                results = {doc_id: True for doc_id, _ in batch_data}
                
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
            # 使用批处理器删除单个文档
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._batch_deleter.add, doc_id)
            
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
            # 使用批处理器删除文档
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._batch_deleter.add_batch, doc_ids)
            
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
    
    async def search_documents(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_expr: Optional[str] = None,
        search_params: Optional[Dict[str, Any]] = None
    ) -> List[NodeWithScore]:
        """执行纯向量搜索（使用LlamaIndex或原生Milvus）

        Args:
            query_vector: 查询向量.
            top_k: 返回的最大结果数.
            filter_expr: Milvus的标量过滤表达式.
            search_params: Milvus搜索参数.
            
        Returns:
            匹配的文档节点列表及分数.
            
        Raises:
            ValueError: 搜索失败.
        """
        if not self._client:
            await self.connect()
                
        try:
            # 1. 验证向量维度
            if len(query_vector) != self.config.dimension:
                raise ValueError(f"查询向量维度不匹配: 预期 {self.config.dimension}, 实际 {len(query_vector)}")
                
            # 2. 确保向量存储已初始化
            if not self.vector_store:
                self._initialize()
                
            # 3. 使用连接池中的客户端执行搜索
            result_nodes = self.vector_store.search(
                query_embedding=query_vector,
                similarity_top_k=top_k,
                filters=self._parse_filter_expr(filter_expr) if filter_expr else None
            )
            
            return result_nodes
            logger.debug(f"Executing Milvus native vector search with args: {search_args}")
            results = self.collection.search(**search_args)

            nodes_with_scores = []
            if results and results[0]:
                milvus_hits = results[0]
                for hit in milvus_hits:
                    if not hit.entity: continue
                    node_id = hit.entity.get(self.config.id_field, hit.id)
                    text = hit.entity.get(self.config.text_field, "")
                    metadata = hit.entity.get(self.config.metadata_field, {})
                    if metadata is None: metadata = {}

                    node = TextNode(id_=str(node_id), text=text, metadata=metadata)
                    nodes_with_scores.append(NodeWithScore(node=node, score=hit.score))

            nodes_with_scores.sort(key=lambda x: x.score, reverse=True)
            logger.info(f"Milvus native vector search returned {len(nodes_with_scores)} results.")
            return nodes_with_scores

        except Exception as e:
            logger.exception(f"执行Milvus原生向量搜索失败: {str(e)}")
            raise ValueError(f"Milvus原生向量搜索失败: {str(e)}")
    
    async def hybrid_search(
        self,
        query_text: str,
        query_vector: List[float],
        top_k: int = 5,
        filter_expr: Optional[str] = None,
        search_params: Optional[Dict[str, Any]] = None
    ) -> List[NodeWithScore]:
        """使用Milvus原生混合搜索功能进行检索

        Args:
            query_text: 用于关键词匹配的查询文本.
            query_vector: 查询向量.
            top_k: 返回的最大结果数.
            filter_expr: Milvus的标量过滤表达式 (例如: "category == 'news'").
                         注意: 这个 filter_expr 会与关键词搜索的 expr 合并.
            search_params: Milvus搜索参数 (例如: {"metric_type": "L2", "params": {"ef": 128}}).

        Returns:
            匹配的文档节点列表及分数.

        Raises:
            ValueError: 搜索失败.
        """
        if not self.collection:
            await self.connect()
            if not self.collection:
                raise ValueError("Milvus数据源未连接或集合不存在")

        try:
            # 1. 构建关键词搜索表达式 (expr)
            #    - 使用 Milvus 支持的表达式语法.
            #    - 基础示例: 使用 'like' 进行模糊匹配 (注意性能和潜在注入风险, 生产环境可能需要更安全的方式).
            #    - 如果文本字段建立了 INVERTED 索引，可以使用更高效的操作符 (e.g., text_match).
            #    - 这里我们假设 text_field 存储了需要匹配的文本.
            #    - 对 query_text 进行必要的清理或转义.
            # TODO: Implement proper escaping or use parameterized queries if supported. Use text_match if INVERTED index exists.
            # Escaping single quotes for basic 'like' safety
            safe_query_text = query_text.replace("'", "''")
            keyword_expr = f"{self.config.text_field} like '%{safe_query_text}%'" # Basic example with escaped quotes

            # 合并传入的 filter_expr 和关键词搜索的 expr
            final_expr = keyword_expr
            if filter_expr:
                final_expr = f"({filter_expr}) and ({keyword_expr})"

            # 2. 准备向量搜索参数 (anns)
            #    - 使用配置中的向量字段名.
            #    - 设置搜索参数 (metric_type, params like ef). 可以从 search_params 参数获取或使用默认值.
            default_search_params = {"metric_type": "L2", "params": {"ef": 10}} # Example defaults
            current_search_params = default_search_params.copy() # Use copy to avoid modifying default
            if search_params:
                current_search_params.update(search_params)

            # 3. 执行原生混合搜索
            #    - output_fields: 指定需要返回的字段, 至少包括 id 和 text 字段，以及元数据字段.
            output_fields = [self.config.id_field, self.config.text_field, self.config.metadata_field]

            search_args = {
                "data": [query_vector], # Query vectors
                "anns_field": self.config.embedding_field, # Vector field name
                "param": current_search_params, # Search parameters
                "limit": top_k,
                "expr": final_expr, # Combined scalar/keyword filter
                "output_fields": output_fields,
                # Optional: Specify a ranker, e.g., RRFRanker() or WeightedRanker(...)
                # Using RRF Ranker as an example default for better fusion
                "ranker": RRFRanker(),
                # "consistency_level": "Strong" # Optional: Adjust consistency level if needed
            }

            logger.debug(f"Executing Milvus native hybrid search with args: {search_args}")
            results = self.collection.search(**search_args)

            # 4. 处理并转换结果
            nodes_with_scores = []
            if results and results[0]: # results is a list of Hit lists, one per query vector
                milvus_hits = results[0]
                for hit in milvus_hits:
                    # Ensure entity exists and has data
                    if not hit.entity:
                        logger.warning(f"Milvus hit for ID {hit.id} has no entity data.")
                        continue

                    node_id = hit.entity.get(self.config.id_field)
                    # Use hit.id as fallback if id_field is not in output or missing
                    if node_id is None:
                         node_id = hit.id

                    text = hit.entity.get(self.config.text_field, "") # Get text content
                    metadata = hit.entity.get(self.config.metadata_field, {})
                    if metadata is None: # Ensure metadata is a dict
                        metadata = {}

                    # LlamaIndex 需要 TextNode
                    node = TextNode(
                        id_=str(node_id), # Ensure ID is string
                        text=text,
                        metadata=metadata
                    )
                    # Note: Milvus RRF score is not directly comparable to cosine similarity.
                    # Adjust score interpretation or normalization if needed elsewhere.
                    nodes_with_scores.append(NodeWithScore(node=node, score=hit.score))

            nodes_with_scores.sort(key=lambda x: x.score, reverse=True) # Ensure sorted by score descending

            logger.info(f"Milvus native hybrid search returned {len(nodes_with_scores)} results.")
            return nodes_with_scores

        except Exception as e:
            logger.exception(f"执行Milvus原生混合搜索失败: {str(e)}") # Use logger.exception to include traceback
            raise ValueError(f"Milvus原生混合搜索失败: {str(e)}")
    
    def _parse_filter_expr(self, expr: str) -> Dict[str, Any]:
        """解析过滤表达式为过滤字典
        
        Args:
            expr: 过滤表达式，如 "file_type == 'pdf'"
            
        Returns:
            过滤字典
        """
        filters = {}
        
        try:
            # 基本语法解析
            if "==" in expr:
                parts = expr.split("==")
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    
                    # 处理引号
                    if value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    elif value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                        
                    filters[key] = value
            elif "!=" in expr:
                # 目前不支持不等于操作符，但为了向前兼容，记录下来
                logger.warning(f"过滤表达式中包含不支持的操作符: {expr}")
                
            logger.debug(f"解析过滤表达式 '{expr}' 为 {filters}")
            return filters
        except Exception as e:
            logger.error(f"解析过滤表达式失败: {str(e)}")
            return {}
    
    async def health_check(self) -> bool:
        """检查Milvus数据源健康状态
        
        Returns:
            是否健康
        """
        try:
            if not self._client:
                self._initialize()
            
            # 检查是否可以连接到Milvus服务器
            is_connected = connections.get_connection_addr('default') is not None
            
            # 检查集合是否存在
            has_collection = utility.has_collection(self.config.collection_name)
            
            return is_connected and has_collection
        except Exception as e:
            logger.error(f"Milvus健康检查失败: {str(e)}")
            return False
    
    async def get_info(self) -> Dict[str, Any]:
        """获取Milvus数据源信息
        
        Returns:
            数据源信息字典
        """
        try:
            if not self._client:
                try:
                    self._initialize()
                except Exception as e:
                    return {
                        "type": "milvus",
                        "uri": self.config.uri,
                        "collection": self.config.collection_name,
                        "is_connected": False,
                        "error": str(e)
                    }
                
            info = {
                "type": "milvus",
                "uri": self.config.uri,
                "collection": self.config.collection_name,
                "dimension": self.config.dimension,
                "is_connected": self._client is not None and self._connected
            }
            
            # 如果集合存在，添加集合信息
            if utility.has_collection(self.config.collection_name):
                if self.collection is None:
                    self.collection = Collection(self.config.collection_name)
                    
                info["collection_exists"] = True
                info["row_count"] = self.collection.num_entities
                info["fields"] = [field.name for field in self.collection.schema.fields]
                
                # 获取索引信息
                if self.collection.has_index():
                    index_info = self.collection.index().to_dict()
                    info["index"] = index_info
            else:
                info["collection_exists"] = False
                
            return info
        except Exception as e:
            logger.error(f"获取Milvus信息失败: {str(e)}")
            return {"type": "milvus", "error": str(e)}
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息
        
        Returns:
            集合统计信息字典
        """
        try:
            if not self._client:
                self._initialize()
                
            # 检查集合是否存在
            if not utility.has_collection(self.config.collection_name):
                return {
                    "name": self.config.collection_name,
                    "exists": False,
                    "error": "集合不存在"
                }
                
            # 加载集合
            if self.collection is None:
                self.collection = Collection(self.config.collection_name)
                
            # 获取统计信息
            stats = {
                "name": self.config.collection_name,
                "exists": True,
                "row_count": self.collection.num_entities,
                "fields": [field.name for field in self.collection.schema.fields]
            }
            
            # 获取索引信息
            if self.collection.has_index():
                index_info = self.collection.index().to_dict()
                stats["index"] = index_info
                
            return stats
        except Exception as e:
            logger.error(f"获取Milvus集合统计信息失败: {str(e)}")
            return {
                "name": self.config.collection_name,
                "exists": utility.has_collection(self.config.collection_name),
                "error": str(e)
            }
    
    async def clear_collection(self) -> bool:
        """清空集合
        
        Returns:
            是否成功
        """
        try:
            if not self._client:
                self._initialize()
                
            # 检查集合是否存在
            if not utility.has_collection(self.config.collection_name):
                logger.warning(f"集合 {self.config.collection_name} 不存在，无需清空")
                return True
                
            # 删除并重建集合
            if self.collection:
                try:
                    self.collection.release()
                except:
                    pass
                self.collection = None
                
            # 删除集合
            utility.drop_collection(self.config.collection_name)
            logger.info(f"已删除集合: {self.config.collection_name}")
            
            # 重新创建集合
            self._initialize()
            logger.info(f"已重新创建集合: {self.config.collection_name}")
            
            return True
        except Exception as e:
            logger.error(f"清空Milvus集合失败: {str(e)}")
            return False 