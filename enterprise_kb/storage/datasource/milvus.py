"""Milvus向量数据库数据源实现"""
import logging
from typing import Any, Dict, List, Optional, Type, ClassVar
from pydantic import Field

from llama_index.core.schema import TextNode, NodeWithScore, BaseNode
from llama_index.vector_stores.milvus import MilvusVectorStore

from enterprise_kb.storage.datasource.base import DataSource, DataSourceConfig
from enterprise_kb.storage.datasource.registry import register_datasource
from enterprise_kb.core.config.settings import settings

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
    
    @classmethod
    def get_config_class(cls) -> Type[MilvusDataSourceConfig]:
        """获取配置类"""
        return cls._config_class
    
    def _initialize(self) -> None:
        """初始化Milvus客户端"""
        try:
            # 延迟导入pymilvus
            from pymilvus import MilvusClient
            
            # 创建连接
            connection_args = {
                "uri": self.config.uri,
                "user": self.config.user,
                "password": self.config.password, 
                "token": ""  # 使用用户名密码认证时不需要token
            }
            
            self._client = MilvusClient(**connection_args)
            
            # 初始化向量存储
            self.vector_store = MilvusVectorStore(
                milvus_client=self._client,
                collection_name=self.config.collection_name,
                dim=self.config.dimension,
                text_field=self.config.text_field,
                embedding_field=self.config.embedding_field,
                metadata_field=self.config.metadata_field,
                id_field=self.config.id_field,
            )
            
            # 获取集合引用
            if self._client.has_collection(self.config.collection_name):
                self.collection = self._client.get_collection(self.config.collection_name)
            
            logger.info(f"成功初始化Milvus客户端连接: {self.config.uri}")
        except Exception as e:
            logger.error(f"初始化Milvus客户端失败: {str(e)}")
            self._client = None
            self.vector_store = None
            self.collection = None
            raise
    
    async def connect(self) -> None:
        """连接到Milvus服务器"""
        if not self._client:
            try:
                self._initialize()
                logger.info(f"成功连接到Milvus数据源: {self.config.uri}")
            except Exception as e:
                logger.error(f"连接Milvus数据源失败: {str(e)}")
                raise
    
    async def disconnect(self) -> None:
        """断开与Milvus服务器的连接"""
        try:
            if self._client:
                # pymilvus会自动管理连接，我们只需要释放引用
                self._client = None
                self.vector_store = None
                self.collection = None
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
            raise ValueError("Milvus数据源未连接")
            
        try:
            # 使用LlamaIndex的向量存储添加节点
            return self.vector_store.add(nodes)
        except Exception as e:
            logger.error(f"添加文档到Milvus失败: {str(e)}")
            raise ValueError(f"添加文档失败: {str(e)}")
    
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
        if not self.vector_store or not self._client:
            raise ValueError("Milvus数据源未连接")
            
        try:
            # 确保新节点的metadata中包含正确的doc_id
            if node.metadata is None:
                node.metadata = {}
            node.metadata["doc_id"] = doc_id
            
            # 第一步：删除旧文档
            await self.delete_document(doc_id)
            
            # 第二步：添加新文档
            self.vector_store.add([node])
            
            return True
        except Exception as e:
            logger.error(f"更新Milvus文档失败: {str(e)}")
            raise ValueError(f"更新文档失败: {str(e)}")
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功
            
        Raises:
            ValueError: 删除失败
        """
        if not self._client:
            raise ValueError("Milvus数据源未连接")
            
        try:
            # 构造过滤表达式，根据doc_id删除
            filter_expr = f"{self.config.metadata_field}['doc_id'] == '{doc_id}'"
            
            # 执行删除
            self._client.delete(
                collection_name=self.config.collection_name,
                filter=filter_expr
            )
            
            return True
        except Exception as e:
            logger.error(f"删除Milvus文档失败: {str(e)}")
            raise ValueError(f"删除文档失败: {str(e)}")
    
    async def search_documents(
        self, 
        query_vector: List[float], 
        top_k: int = 5, 
        filter_expr: Optional[str] = None
    ) -> List[NodeWithScore]:
        """搜索文档
        
        Args:
            query_vector: 查询向量
            top_k: 返回的最大结果数
            filter_expr: 过滤表达式
            
        Returns:
            匹配的文档节点列表
            
        Raises:
            ValueError: 搜索失败
        """
        if not self.vector_store:
            raise ValueError("Milvus数据源未连接")
            
        try:
            # 构建查询
            from llama_index.core.vector_stores.types import VectorStoreQuery
            
            query = VectorStoreQuery(
                query_embedding=query_vector,
                similarity_top_k=top_k,
                filters=self._parse_filter_expr(filter_expr) if filter_expr else None
            )
            
            # 执行查询
            results = self.vector_store.query(query)
            return results
        except Exception as e:
            logger.error(f"搜索Milvus文档失败: {str(e)}")
            raise ValueError(f"搜索文档失败: {str(e)}")
    
    def _parse_filter_expr(self, expr: str) -> Dict[str, Any]:
        """解析过滤表达式为过滤字典
        
        Args:
            expr: 过滤表达式，如 "file_type == 'pdf'"
            
        Returns:
            过滤字典
        """
        filters = {}
        
        # 简单解析，仅支持等于表达式
        if "==" in expr:
            parts = expr.split("==")
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                
                # 移除引号
                if (value.startswith("'") and value.endswith("'")) or \
                   (value.startswith('"') and value.endswith('"')):
                    value = value[1:-1]
                    
                filters[key] = value
                
        return filters
    
    async def health_check(self) -> bool:
        """检查Milvus数据源健康状态
        
        Returns:
            是否健康
        """
        try:
            if not self._client:
                return False
            
            # 尝试获取集合列表
            collections = self._client.list_collections()
            return True
        except Exception as e:
            logger.error(f"Milvus健康检查失败: {str(e)}")
            return False
    
    async def get_info(self) -> Dict[str, Any]:
        """获取Milvus数据源信息
        
        Returns:
            数据源信息
        """
        info = {
            "type": self.source_type,
            "name": self.config.name,
            "description": self.config.description,
            "uri": self.config.uri,
            "collection_name": self.config.collection_name,
            "dimension": self.config.dimension,
            "is_connected": False
        }
        
        try:
            if self._client:
                info["is_connected"] = True
                
                # 尝试获取集合信息
                if self._client.has_collection(self.config.collection_name):
                    # 获取集合统计信息
                    stats = self._client.get_collection_stats(self.config.collection_name)
                    if "row_count" in stats:
                        info["row_count"] = stats["row_count"]
                else:
                    info["row_count"] = 0
        except Exception as e:
            logger.error(f"获取Milvus信息失败: {str(e)}")
        
        return info 