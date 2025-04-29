"""Milvus向量数据库数据源实现"""
import logging
from typing import Any, Dict, List, Optional, Type, ClassVar, Tuple, Union
from pydantic import Field

from llama_index.core.schema import TextNode, NodeWithScore, BaseNode
from llama_index.vector_stores.milvus import MilvusVectorStore, IndexManagement
from pymilvus import Collection, utility, connections

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
        """更新文档
        
        Milvus不支持直接更新操作，因此我们需要删除旧文档并添加新文档
        
        Args:
            doc_id: 文档ID
            node: 新的文档节点
            
        Returns:
            是否成功
            
        Raises:
            ValueError: 更新失败
        """
        if not self.vector_store:
            await self.connect()
            if not self.vector_store:
                raise ValueError("Milvus数据源未连接")
            
        try:
            # 确保新节点的metadata中包含正确的doc_id
            if node.metadata is None:
                node.metadata = {}
            node.metadata["doc_id"] = doc_id
            
            # 第一步：删除旧文档
            deleted = await self.delete_document(doc_id)
            if not deleted:
                logger.warning(f"更新文档前删除旧文档失败: {doc_id}")
            
            # 第二步：添加新文档
            self.vector_store.add([node])
            
            logger.info(f"成功更新文档: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"更新Milvus文档失败: {str(e)}")
            raise ValueError(f"更新文档失败: {str(e)}")
    
    async def batch_update_documents(self, updates: List[Tuple[str, BaseNode]]) -> Dict[str, bool]:
        """批量更新文档
        
        Args:
            updates: 元组列表，每个元组包含 (doc_id, new_node)
            
        Returns:
            文档ID及其更新结果的字典
            
        Raises:
            ValueError: 更新失败
        """
        if not self.vector_store:
            await self.connect()
            if not self.vector_store:
                raise ValueError("Milvus数据源未连接")
            
        results = {}
        try:
            # 1. 收集所有要删除的doc_ids
            doc_ids = [doc_id for doc_id, _ in updates]
            
            # 2. 批量删除
            deleted = await self.batch_delete_documents(doc_ids)
            
            # 3. 准备新节点
            nodes = []
            for doc_id, node in updates:
                if node.metadata is None:
                    node.metadata = {}
                node.metadata["doc_id"] = doc_id
                nodes.append(node)
                
                # 记录删除结果
                results[doc_id] = deleted.get(doc_id, False)
            
            # 4. 批量添加
            if nodes:
                self.vector_store.add(nodes)
                
                # 更新结果为成功
                for doc_id in results:
                    results[doc_id] = True
                
                logger.info(f"成功批量更新 {len(updates)} 个文档")
            else:
                logger.warning("批量更新没有有效节点可添加")
                
            return results
        except Exception as e:
            logger.error(f"批量更新Milvus文档失败: {str(e)}")
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
        if not self.vector_store or not self._client:
            await self.connect()
            if not self.vector_store or not self._client:
                raise ValueError("Milvus数据源未连接")
            
        try:
            # 使用客户端的 delete_by_doc_id 方法
            if self._client:
                try:
                    delete_count = self._client.delete_by_doc_id(doc_id)
                    success = delete_count > 0
                    logger.info(f"删除文档 {doc_id}: {'成功' if success else '未找到匹配记录'}")
                    return success
                except Exception as e:
                    logger.error(f"删除文档 {doc_id} 失败: {str(e)}")
                    return False
            else:
                logger.error(f"删除文档前Milvus客户端未初始化")
                return False
        except Exception as e:
            logger.error(f"删除Milvus文档失败: {str(e)}")
            raise ValueError(f"删除文档失败: {str(e)}")
    
    async def batch_delete_documents(self, doc_ids: List[str]) -> Dict[str, bool]:
        """批量删除文档
        
        Args:
            doc_ids: 文档ID列表
            
        Returns:
            文档ID及其删除结果的字典
            
        Raises:
            ValueError: 删除失败
        """
        if not self.vector_store or not self._client:
            await self.connect()
            if not self.vector_store or not self._client:
                raise ValueError("Milvus数据源未连接")
            
        results = {doc_id: False for doc_id in doc_ids}
        
        try:
            # 如果没有文档ID，直接返回空结果
            if not doc_ids:
                logger.warning("批量删除传入了空的文档ID列表")
                return results
            
            # 逐个删除文档
            for doc_id in doc_ids:
                try:
                    success = await self.delete_document(doc_id)
                    results[doc_id] = success
                except Exception as e:
                    logger.warning(f"删除文档 {doc_id} 失败: {str(e)}")
                    results[doc_id] = False
                    
            # 统计成功删除的数量
            success_count = sum(1 for success in results.values() if success)
            logger.info(f"批量删除操作完成，成功删除了 {success_count}/{len(doc_ids)} 条记录")
            return results
        except Exception as e:
            logger.error(f"批量删除Milvus文档失败: {str(e)}")
            raise ValueError(f"批量删除文档失败: {str(e)}")
    
    async def search_documents(
        self, 
        query_vector: List[float], 
        top_k: int = 5, 
        filter_expr: Optional[str] = None,
        search_params: Optional[Dict[str, Any]] = None
    ) -> List[NodeWithScore]:
        """搜索文档
        
        Args:
            query_vector: 查询向量
            top_k: 返回的最大结果数
            filter_expr: 过滤表达式
            search_params: 搜索参数，例如 {"nprobe": 10, "ef": 64}
            
        Returns:
            匹配的文档节点列表
            
        Raises:
            ValueError: 搜索失败
        """
        if not self.vector_store:
            await self.connect()
            if not self.vector_store:
                raise ValueError("Milvus数据源未连接")
            
        try:
            # 构建查询
            from llama_index.core.vector_stores.types import VectorStoreQuery, MetadataFilters
            
            # 解析元数据过滤器
            metadata_filters = None
            if filter_expr:
                filters_dict = self._parse_filter_expr(filter_expr)
                if filters_dict:
                    metadata_filters = MetadataFilters.from_dict(filters_dict)
            
            # 创建查询对象
            query = VectorStoreQuery(
                query_embedding=query_vector,
                similarity_top_k=top_k,
                filters=metadata_filters
            )
            
            # 设置搜索参数（如果提供）
            if search_params:
                self.vector_store.search_params = search_params
            
            # 执行查询
            results = self.vector_store.query(query)
            logger.info(f"向量搜索完成，返回 {len(results.nodes)} 条结果")
            return results.nodes
        except Exception as e:
            logger.error(f"搜索Milvus文档失败: {str(e)}")
            raise ValueError(f"搜索文档失败: {str(e)}")
    
    async def hybrid_search(
        self,
        query_text: str,
        query_vector: List[float],
        top_k: int = 5,
        text_weight: float = 0.5,
        vector_weight: float = 0.5,
        filter_expr: Optional[str] = None
    ) -> List[NodeWithScore]:
        """混合搜索：同时使用文本和向量进行搜索
        
        Args:
            query_text: 查询文本
            query_vector: 查询向量
            top_k: 返回的最大结果数
            text_weight: 文本搜索权重
            vector_weight: 向量搜索权重
            filter_expr: 过滤表达式
            
        Returns:
            匹配的文档节点列表
            
        Raises:
            ValueError: 搜索失败
        """
        if not self.vector_store or not self.collection:
            await self.connect()
            if not self.vector_store or not self.collection:
                raise ValueError("Milvus数据源未连接")
            
        try:
            # 使用向量搜索获取结果
            vector_results = await self.search_documents(
                query_vector=query_vector,
                top_k=top_k * 2,  # 扩大搜索范围，以便后续重排序
                filter_expr=filter_expr
            )
            
            if not vector_results:
                logger.info("向量搜索未返回结果，无法进行混合搜索")
                return []
            
            # 由于Milvus 2.x还不完全支持混合搜索，我们使用后处理手动实现混合排序
            # 基于向量相似度和文本相关性进行重排序
            from rapidfuzz import fuzz
            
            # 计算文本相似度分数
            text_scores = {}
            for node in vector_results:
                # 使用模糊匹配计算文本相似度
                if hasattr(node, "node") and hasattr(node.node, "text"):
                    node_text = node.node.text
                    text_similarity = fuzz.token_sort_ratio(query_text.lower(), node_text.lower()) / 100.0
                    text_scores[node.node.id_] = text_similarity
                else:
                    text_scores[node.node.id_] = 0.0
            
            # 合并分数
            hybrid_scores = {}
            for node in vector_results:
                node_id = node.node.id_
                vector_score = node.score if node.score is not None else 0.0
                text_score = text_scores.get(node_id, 0.0)
                
                # 计算混合分数
                hybrid_score = (vector_score * vector_weight) + (text_score * text_weight)
                hybrid_scores[node_id] = hybrid_score
                
                # 更新节点分数
                node.score = hybrid_score
            
            # 根据混合分数重新排序
            sorted_results = sorted(vector_results, key=lambda x: hybrid_scores.get(x.node.id_, 0.0), reverse=True)
            
            # 限制结果数量
            final_results = sorted_results[:top_k]
            
            logger.info(f"混合搜索完成，返回 {len(final_results)} 条结果")
            return final_results
            
        except Exception as e:
            logger.error(f"混合搜索失败: {str(e)}")
            raise ValueError(f"混合搜索失败: {str(e)}")
    
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