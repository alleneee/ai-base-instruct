"""Milvus向量数据库数据源实现"""
import logging
from typing import Any, Dict, List, Optional, Type, ClassVar, Tuple, Union
from pydantic import Field

from llama_index.core.schema import TextNode, NodeWithScore, BaseNode
from llama_index.vector_stores.milvus import MilvusVectorStore, IndexManagement
from pymilvus import Collection, utility, connections, RRFRanker

from enterprise_kb.storage.datasource.base import DataSource, DataSourceConfig
from enterprise_kb.storage.datasource.registry import register_datasource
from enterprise_kb.core.config.settings import settings
from enterprise_kb.utils.milvus_client import get_milvus_client

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
    
    @classmethod
    def get_config_class(cls) -> Type[MilvusDataSourceConfig]:
        """获取配置类"""
        return cls._config_class
    
    def _initialize(self) -> None:
        """初始化Milvus客户端"""
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
            
            # 获取Milvus客户端
            self._client = get_milvus_client()
            
            # 如果集合存在，加载集合
            if utility.has_collection(self.config.collection_name):
                self.collection = Collection(self.config.collection_name)
            
            logger.info(f"成功初始化Milvus向量存储: {uri}")
        except Exception as e:
            logger.error(f"初始化Milvus数据源失败: {str(e)}")
            raise ValueError(f"初始化Milvus数据源失败: {str(e)}")
    
    async def connect(self) -> None:
        """连接到Milvus服务器"""
        if not self._client or not self._connected:
            try:
                self._initialize()
                # 如果集合存在，加载到内存
                if self.collection:
                    self.collection.load()
                self._connected = True
                logger.info(f"成功连接到Milvus数据源: {self.config.uri}")
            except Exception as e:
                self._connected = False
                logger.error(f"连接Milvus数据源失败: {str(e)}")
                raise
    
    async def disconnect(self) -> None:
        """断开与Milvus服务器的连接"""
        try:
            if self.collection:
                try:
                    self.collection.release()
                except Exception as inner_e:
                    logger.warning(f"释放Milvus集合资源异常: {str(inner_e)}")
                
            if self._client:
                # pymilvus会自动管理连接，我们只需要释放引用
                self._client.close()
                self._client = None
                self.vector_store = None
                self.collection = None
                self._connected = False
                logger.info("已断开与Milvus数据源的连接")
        except Exception as e:
            logger.error(f"断开Milvus数据源连接失败: {str(e)}")

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
        """批量添加文档到Milvus，分批处理减少内存消耗
        
        Args:
            nodes: 文档节点列表
            batch_size: 批量大小
            
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
            all_node_ids = []
            
            # 分批处理
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i:i+batch_size]
                batch_ids = self.vector_store.add(batch)
                all_node_ids.extend(batch_ids)
                logger.info(f"成功添加第 {i//batch_size + 1} 批数据 ({len(batch)} 条) 到Milvus")
                
            logger.info(f"批量添加完成，总共添加 {len(all_node_ids)} 条数据")
            return all_node_ids
        except Exception as e:
            logger.error(f"批量添加文档到Milvus失败: {str(e)}")
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
        """批量更新/插入文档 (通过Upsert实现)

        Args:
            updates: 元组列表，每个元组包含 (doc_id, new_node).
                     new_node 必须包含 embedding.
            batch_size: 传递给 batch_add_documents 的批量大小.

        Returns:
            文档ID及其操作结果的字典 (如果batch_add_documents成功，则都为True).

        Raises:
            ValueError: 更新失败或数据源未连接.
        """
        if not self.vector_store:
            await self.connect()
            if not self.vector_store:
                raise ValueError("Milvus数据源未连接")

        nodes_to_upsert = []
        results = {}
        try:
            # 1. 准备所有要 upsert 的节点
            for doc_id, node in updates:
                # 设置节点ID为主键
                node.id_ = doc_id
                nodes_to_upsert.append(node)
                # Assume success unless batch_add throws an error
                results[doc_id] = True 

            # 2. 调用批量添加 (add -> upsert)
            if nodes_to_upsert:
                await self.batch_add_documents(nodes_to_upsert, batch_size=batch_size)
                logger.info(f"成功批量 Upsert {len(nodes_to_upsert)} 个文档")
            else:
                logger.warning("批量 Upsert 没有提供有效节点")

            return results
        except Exception as e:
            logger.exception(f"批量 Upsert Milvus 文档失败: {str(e)}")
            # Mark all as failed on exception
            for doc_id, _ in updates:
                 results[doc_id] = False
            raise ValueError(f"批量 Upsert 文档失败: {str(e)}")
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功
            
        Raises:
            ValueError: 删除失败
        """
        if not self.vector_store or not self._client:
            # Deletion might still require the client if vector_store.delete is not used or sufficient
            # Let's ensure connection and client exist for deletion logic below
             await self.connect()
             if not self.vector_store or not self._client or not self.collection:
                 raise ValueError("Milvus数据源未连接或初始化失败")

        try:
            # Option 1: Use LlamaIndex vector_store delete if it maps correctly
            # self.vector_store.delete(ref_doc_id=doc_id) # Check LlamaIndex documentation for exact method/params

            # Option 2: Use direct pymilvus client delete (more reliable control)
            # Requires the collection object to be loaded.
            expr = f"{self.config.id_field} == '{doc_id}'" # Assuming id_field is the primary key field name
            logger.debug(f"Attempting to delete document using expr: {expr}")
            delete_result = self.collection.delete(expr=expr)
            # delete_result might be DeleteResult object or similar, check pymilvus docs
            # For simplicity, let's assume success if no exception
            # We might not know the exact count if multiple segments are involved before compaction.
            logger.info(f"删除文档 (doc_id: {doc_id}) 操作已执行 (可能需要时间生效)")
            # Milvus delete is often asynchronous in effect due to compaction.
            # Returning True indicates the command was sent.
            return True

        except Exception as e:
            logger.exception(f"删除Milvus文档失败 (doc_id: {doc_id}): {str(e)}")
            raise ValueError(f"删除文档失败 (doc_id: {doc_id}): {str(e)}")
    
    async def batch_delete_documents(self, doc_ids: List[str]) -> Dict[str, bool]:
        """批量删除文档
        
        Args:
            doc_ids: 文档ID列表
            
        Returns:
            文档ID及其删除结果的字典
            
        Raises:
            ValueError: 删除失败
        """
        if not self.vector_store or not self._client or not self.collection:
             await self.connect()
             if not self.vector_store or not self._client or not self.collection:
                 raise ValueError("Milvus数据源未连接或初始化失败")

        results = {doc_id: False for doc_id in doc_ids}
        if not doc_ids:
            logger.warning("批量删除传入了空的文档ID列表")
            return results

        try:
            # Use Milvus batch delete via expression
            # Ensure IDs are properly formatted for the expression (e.g., strings quoted)
            quoted_ids = [f"'{doc_id}'" for doc_id in doc_ids]
            expr = f"{self.config.id_field} in [{','.join(quoted_ids)}]"
            logger.debug(f"Attempting to batch delete documents using expr: {expr}")

            delete_result = self.collection.delete(expr=expr)
            # Assume success if command sent without error
            for doc_id in doc_ids:
                results[doc_id] = True
            logger.info(f"批量删除 {len(doc_ids)} 个文档的操作已执行 (可能需要时间生效)")
            return results
        except Exception as e:
            logger.exception(f"批量删除Milvus文档失败: {str(e)}")
            # Keep results as False on failure
            raise ValueError(f"批量删除文档失败: {str(e)}")
    
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
        """
        if not self.collection:
            await self.connect()
            if not self.collection:
                raise ValueError("Milvus数据源未连接或集合不存在")

        try:
            default_search_params = {"metric_type": "L2", "params": {"ef": 10}}
            current_search_params = default_search_params.copy()
            if search_params:
                current_search_params.update(search_params)

            output_fields = [self.config.id_field, self.config.text_field, self.config.metadata_field]

            search_args = {
                "data": [query_vector],
                "anns_field": self.config.embedding_field,
                "param": current_search_params,
                "limit": top_k,
                "expr": filter_expr,
                "output_fields": output_fields,
            }

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