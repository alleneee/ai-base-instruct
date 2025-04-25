"""PostgreSQL向量数据库数据源实现"""
import logging
from typing import Any, Dict, List, Optional, Type, ClassVar
from pydantic import Field
import asyncpg

from llama_index.core.schema import TextNode, NodeWithScore, BaseNode
from llama_index.vector_stores.postgres import PGVectorStore as LlamaIndexPGStore

from enterprise_kb.storage.datasource.base import DataSource, DataSourceConfig
from enterprise_kb.storage.datasource.registry import register_datasource
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)


class PostgresDataSourceConfig(DataSourceConfig):
    """PostgreSQL数据源配置"""
    
    connection_string: str = Field(settings.POSTGRES_CONNECTION_STRING, description="连接字符串")
    schema_name: str = Field(settings.POSTGRES_SCHEMA_NAME, description="模式名称")
    table_name: str = Field(settings.POSTGRES_TABLE_NAME, description="表名称")
    vector_column: str = Field(settings.POSTGRES_VECTOR_COLUMN, description="向量列名")
    content_column: str = Field(settings.POSTGRES_CONTENT_COLUMN, description="内容列名")
    metadata_column: str = Field(settings.POSTGRES_METADATA_COLUMN, description="元数据列名")
    dimension: int = Field(settings.POSTGRES_DIMENSION, description="向量维度")


@register_datasource("postgres")
class PostgresDataSource(DataSource[PostgresDataSourceConfig]):
    """PostgreSQL向量数据库数据源"""
    
    _config_class: ClassVar[Type[PostgresDataSourceConfig]] = PostgresDataSourceConfig
    
    def __init__(self, config: PostgresDataSourceConfig):
        """初始化PostgreSQL数据源
        
        Args:
            config: PostgreSQL数据源配置
        """
        super().__init__(config)
        self.conn_pool = None
        self.vector_store = None
    
    @classmethod
    def get_config_class(cls) -> Type[PostgresDataSourceConfig]:
        """获取配置类"""
        return cls._config_class
    
    def _initialize(self) -> None:
        """初始化PostgreSQL客户端和向量存储"""
        pass  # 延迟初始化，在connect方法中执行
    
    async def connect(self) -> None:
        """连接到PostgreSQL服务器并初始化向量存储"""
        try:
            # 创建连接池
            self.conn_pool = await asyncpg.create_pool(self.config.connection_string)
            
            # 使用LlamaIndex的PG向量存储
            self.vector_store = LlamaIndexPGStore.from_params(
                connection_string=self.config.connection_string,
                table_name=self.config.table_name,
                schema_name=self.config.schema_name,
                embed_dim=self.config.dimension,
                vector_column=self.config.vector_column,
                content_column=self.config.content_column,
                metadata_column=self.config.metadata_column,
            )
            
            # 检查表是否存在，如果不存在则会在首次使用时创建
            async with self.conn_pool.acquire() as conn:
                table_exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = $1 AND table_name = $2
                    )
                    """,
                    self.config.schema_name, self.config.table_name
                )
                
                if not table_exists:
                    logger.info(f"表 {self.config.schema_name}.{self.config.table_name} 不存在，将在首次使用时创建")
            
            logger.info(f"成功连接到PostgreSQL数据源: {self.config.connection_string}")
        except Exception as e:
            logger.error(f"连接PostgreSQL数据源失败: {str(e)}")
            raise
    
    async def disconnect(self) -> None:
        """断开与PostgreSQL服务器的连接"""
        try:
            if self.conn_pool:
                await self.conn_pool.close()
                self.conn_pool = None
            
            self.vector_store = None
            logger.info("已断开与PostgreSQL数据源的连接")
        except Exception as e:
            logger.error(f"断开PostgreSQL数据源连接失败: {str(e)}")
    
    async def add_documents(self, nodes: List[BaseNode]) -> List[str]:
        """添加文档到PostgreSQL
        
        Args:
            nodes: 文档节点列表
            
        Returns:
            添加成功的节点ID列表
            
        Raises:
            ValueError: 添加失败
        """
        if not self.vector_store:
            raise ValueError("PostgreSQL数据源未连接")
            
        try:
            return self.vector_store.add(nodes)
        except Exception as e:
            logger.error(f"添加文档到PostgreSQL失败: {str(e)}")
            raise ValueError(f"添加文档失败: {str(e)}")
    
    async def update_document(self, doc_id: str, node: BaseNode) -> bool:
        """更新文档
        
        Args:
            doc_id: 文档ID
            node: 新的文档节点
            
        Returns:
            是否成功
            
        Raises:
            ValueError: 更新失败
        """
        if not self.vector_store:
            raise ValueError("PostgreSQL数据源未连接")
            
        try:
            # 确保新节点的metadata中包含正确的doc_id
            if node.metadata is None:
                node.metadata = {}
            node.metadata["doc_id"] = doc_id
            
            # PostgreSQL支持直接更新，使用upsert逻辑
            # 先尝试删除再添加，以确保更新
            await self.delete_document(doc_id)
            self.vector_store.add([node])
            return True
        except Exception as e:
            logger.error(f"更新PostgreSQL文档失败: {str(e)}")
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
        if not self.vector_store:
            raise ValueError("PostgreSQL数据源未连接")
            
        try:
            await self._execute_delete_query(doc_id)
            return True
        except Exception as e:
            logger.error(f"删除PostgreSQL文档失败: {str(e)}")
            raise ValueError(f"删除文档失败: {str(e)}")
    
    async def _execute_delete_query(self, doc_id: str) -> None:
        """执行删除查询
        
        由于LlamaIndex的PGVectorStore没有直接提供删除方法，我们需要手动实现
        
        Args:
            doc_id: 文档ID
        """
        if not self.conn_pool:
            raise ValueError("PostgreSQL连接池未初始化")
            
        query = f"""
        DELETE FROM {self.config.schema_name}.{self.config.table_name}
        WHERE {self.config.metadata_column}->>'doc_id' = $1
        """
        
        async with self.conn_pool.acquire() as conn:
            await conn.execute(query, doc_id)
    
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
            raise ValueError("PostgreSQL数据源未连接")
            
        try:
            # 构建查询
            from llama_index.core.vector_stores.types import VectorStoreQuery
            
            query = VectorStoreQuery(
                query_embedding=query_vector,
                similarity_top_k=top_k,
                # 将过滤表达式转换为过滤字典
                filters=self._parse_filter_expr(filter_expr) if filter_expr else None
            )
            
            # 执行查询
            results = self.vector_store.query(query)
            return results
        except Exception as e:
            logger.error(f"搜索PostgreSQL文档失败: {str(e)}")
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
        """检查PostgreSQL数据源健康状态
        
        Returns:
            是否健康
        """
        try:
            if not self.conn_pool:
                return False
            
            # 尝试简单查询
            async with self.conn_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            return True
        except Exception as e:
            logger.error(f"PostgreSQL健康检查失败: {str(e)}")
            return False
    
    async def get_info(self) -> Dict[str, Any]:
        """获取PostgreSQL数据源信息
        
        Returns:
            数据源信息
        """
        info = {
            "type": self.source_type,
            "name": self.config.name,
            "description": self.config.description,
            "connection_string": self.config.connection_string.replace("://", "://*****:*****@"),  # 隐藏敏感信息
            "schema_name": self.config.schema_name,
            "table_name": self.config.table_name,
            "is_connected": False,
        }
        
        try:
            # 检查连接状态
            if self.conn_pool:
                info["is_connected"] = True
                
                # 尝试获取表行数
                async with self.conn_pool.acquire() as conn:
                    table_exists = await conn.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = $1 AND table_name = $2
                        )
                        """,
                        self.config.schema_name, self.config.table_name
                    )
                    
                    if table_exists:
                        count = await conn.fetchval(
                            f"SELECT COUNT(*) FROM {self.config.schema_name}.{self.config.table_name}"
                        )
                        info["row_count"] = count
                    else:
                        info["row_count"] = 0
        except Exception as e:
            logger.error(f"获取PostgreSQL信息失败: {str(e)}")
        
        return info 