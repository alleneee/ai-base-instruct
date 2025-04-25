"""向量存储管理器模块，用于管理多个向量数据源"""
import logging
from typing import Dict, List, Optional, Any, Type, Union
import asyncio
from pydantic import BaseModel, Field

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import BaseNode, NodeWithScore, TextNode
from llama_index.core.vector_stores.types import VectorStoreQuery

from enterprise_kb.storage.datasource import DataSource, DataSourceFactory, DataSourceConfig
from enterprise_kb.storage.datasource.registry import list_datasource_types

logger = logging.getLogger(__name__)


class VectorStoreInfo(BaseModel):
    """向量存储信息"""
    
    name: str = Field(..., description="向量存储名称")
    description: Optional[str] = Field(None, description="向量存储描述")
    type: str = Field(..., description="向量存储类型")
    is_connected: bool = Field(False, description="是否已连接")
    additional_info: Dict[str, Any] = Field(default_factory=dict, description="附加信息")


class VectorStoreManager:
    """向量存储管理器，管理多个向量数据源"""
    
    def __init__(self):
        """初始化向量存储管理器"""
        self.data_sources: Dict[str, DataSource] = {}
        self.vector_stores: Dict[str, Any] = {}
        self.indices: Dict[str, VectorStoreIndex] = {}
    
    async def add_data_source(
        self, 
        source_type: str, 
        name: str, 
        config: Dict[str, Any]
    ) -> str:
        """添加数据源
        
        Args:
            source_type: 数据源类型
            name: 数据源名称
            config: 数据源配置
            
        Returns:
            数据源名称
            
        Raises:
            ValueError: 数据源名称已存在或创建失败
        """
        if name in self.data_sources:
            raise ValueError(f"数据源名称 '{name}' 已存在")
            
        try:
            # 确保配置中包含名称
            config["name"] = name
            
            # 创建数据源
            datasource = DataSourceFactory.create(source_type, config)
            
            # 连接到数据源
            await datasource.connect()
            
            # 存储数据源和向量存储引用
            self.data_sources[name] = datasource
            if hasattr(datasource, "vector_store"):
                self.vector_stores[name] = datasource.vector_store
                
                # 创建LlamaIndex索引
                index = VectorStoreIndex.from_vector_store(self.vector_stores[name])
                self.indices[name] = index
            
            logger.info(f"添加数据源: {name} ({source_type})")
            return name
        except Exception as e:
            logger.error(f"添加数据源失败: {str(e)}")
            raise ValueError(f"添加数据源失败: {str(e)}")
    
    async def remove_data_source(self, name: str) -> bool:
        """移除数据源
        
        Args:
            name: 数据源名称
            
        Returns:
            是否成功
        """
        if name not in self.data_sources:
            logger.warning(f"数据源 '{name}' 不存在")
            return False
            
        try:
            # 断开连接
            await self.data_sources[name].disconnect()
            
            # 移除引用
            del self.data_sources[name]
            self.vector_stores.pop(name, None)
            self.indices.pop(name, None)
            
            logger.info(f"移除数据源: {name}")
            return True
        except Exception as e:
            logger.error(f"移除数据源失败: {str(e)}")
            return False
    
    async def get_data_source_info(self, name: str) -> Optional[VectorStoreInfo]:
        """获取数据源信息
        
        Args:
            name: 数据源名称
            
        Returns:
            数据源信息，如果不存在则返回None
        """
        if name not in self.data_sources:
            return None
            
        try:
            # 获取数据源信息
            datasource = self.data_sources[name]
            info = await datasource.get_info()
            
            return VectorStoreInfo(
                name=info.get("name", name),
                description=info.get("description"),
                type=info.get("type", datasource.source_type),
                is_connected=info.get("is_connected", False),
                additional_info={
                    k: v for k, v in info.items()
                    if k not in ["name", "description", "type", "is_connected"]
                }
            )
        except Exception as e:
            logger.error(f"获取数据源信息失败: {str(e)}")
            return None
    
    async def list_data_sources(self) -> List[VectorStoreInfo]:
        """列出所有数据源
        
        Returns:
            数据源信息列表
        """
        result = []
        
        for name in self.data_sources:
            info = await self.get_data_source_info(name)
            if info:
                result.append(info)
                
        return result
    
    async def health_check(self, name: Optional[str] = None) -> Dict[str, bool]:
        """检查数据源健康状态
        
        Args:
            name: 数据源名称，如果为None则检查所有数据源
            
        Returns:
            健康状态字典，键为数据源名称，值为是否健康
        """
        result = {}
        
        if name:
            if name not in self.data_sources:
                return {name: False}
                
            result[name] = await self.data_sources[name].health_check()
        else:
            for source_name, datasource in self.data_sources.items():
                result[source_name] = await datasource.health_check()
                
        return result
    
    async def add_nodes(self, nodes: List[BaseNode], datasource_name: str) -> List[str]:
        """添加节点到指定数据源
        
        Args:
            nodes: 节点列表
            datasource_name: 数据源名称
            
        Returns:
            节点ID列表
            
        Raises:
            ValueError: 数据源不存在或添加失败
        """
        if datasource_name not in self.vector_stores:
            raise ValueError(f"数据源 '{datasource_name}' 不存在或不支持向量存储")
            
        try:
            vector_store = self.vector_stores[datasource_name]
            return vector_store.add(nodes)
        except Exception as e:
            logger.error(f"添加节点失败: {str(e)}")
            raise ValueError(f"添加节点失败: {str(e)}")
    
    async def delete_nodes(self, doc_id: str, datasource_name: Optional[str] = None) -> bool:
        """删除节点
        
        Args:
            doc_id: 文档ID
            datasource_name: 数据源名称，如果为None则从所有数据源删除
            
        Returns:
            是否成功
        """
        success = True
        
        try:
            if datasource_name:
                if datasource_name not in self.vector_stores:
                    return False
                    
                vector_stores = [self.vector_stores[datasource_name]]
            else:
                vector_stores = list(self.vector_stores.values())
                
            for vector_store in vector_stores:
                try:
                    if hasattr(vector_store, "delete"):
                        vector_store.delete(doc_id)
                except Exception as e:
                    logger.error(f"删除节点失败: {str(e)}")
                    success = False
                    
            return success
        except Exception as e:
            logger.error(f"删除节点失败: {str(e)}")
            return False
    
    async def query(
        self, 
        query_embedding: List[float],
        datasource_name: Optional[str] = None,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[NodeWithScore]:
        """查询向量
        
        Args:
            query_embedding: 查询向量
            datasource_name: 数据源名称，如果为None则查询所有数据源
            top_k: 返回的最大结果数
            filters: 过滤条件
            
        Returns:
            匹配节点列表
        """
        all_results: List[NodeWithScore] = []
        
        try:
            if datasource_name:
                if datasource_name not in self.indices:
                    return []
                    
                sources = {datasource_name: self.indices[datasource_name]}
            else:
                sources = self.indices
                
            # 构建查询
            query = VectorStoreQuery(
                query_embedding=query_embedding,
                similarity_top_k=top_k,
                filters=filters
            )
                
            # 查询所有数据源
            for name, index in sources.items():
                try:
                    retriever = index.as_retriever(similarity_top_k=top_k)
                    nodes = retriever.retrieve(query)
                    all_results.extend(nodes)
                except Exception as e:
                    logger.error(f"查询数据源 '{name}' 失败: {str(e)}")
                    
            # 对结果排序
            all_results.sort(key=lambda x: x.score if hasattr(x, "score") else 0, reverse=True)
            
            # 限制结果数量
            return all_results[:top_k]
        except Exception as e:
            logger.error(f"查询失败: {str(e)}")
            return []
    
    @classmethod
    def list_available_datasource_types(cls) -> Dict[str, str]:
        """获取所有可用的数据源类型
        
        Returns:
            数据源类型字典，键为类型名称，值为描述
        """
        return list_datasource_types()
            

# 创建单例实例
_vector_store_manager = None

def get_vector_store_manager() -> VectorStoreManager:
    """获取向量存储管理器单例"""
    global _vector_store_manager
    if _vector_store_manager is None:
        _vector_store_manager = VectorStoreManager()
    return _vector_store_manager 