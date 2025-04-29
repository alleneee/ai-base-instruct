"""
向量数据库工厂模块
负责创建和管理向量数据库实例
"""
from typing import Dict, Optional, Any, Type, Union
import logging

from enterprise_kb.storage.vector_store.base import VectorStoreBase
from enterprise_kb.storage.vector_store.milvus_store import MilvusVectorStore
from enterprise_kb.storage.vector_store.elasticsearch_store import ElasticsearchVectorStore
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

class VectorStoreFactory:
    """
    向量数据库工厂类
    
    负责创建不同类型的向量数据库实例，实现向量存储的无缝切换
    """
    
    # 向量数据库类型映射
    _store_types: Dict[str, Type[VectorStoreBase]] = {
        "milvus": MilvusVectorStore,
        "elasticsearch": ElasticsearchVectorStore,
    }
    
    # 单例实例缓存
    _instances: Dict[str, VectorStoreBase] = {}
    
    @classmethod
    def get_vector_store(cls, 
                        store_type: Optional[str] = None, 
                        config: Optional[Dict[str, Any]] = None) -> VectorStoreBase:
        """
        获取向量数据库实例
        
        Args:
            store_type: 向量数据库类型，如 'milvus' 或 'elasticsearch'，默认使用配置文件中的值
            config: 向量数据库配置参数，默认为None
            
        Returns:
            VectorStoreBase: 向量数据库实例
            
        Raises:
            ValueError: 如果指定的向量数据库类型不支持
        """
        # 获取向量数据库类型，优先使用参数，其次使用配置文件
        vector_store_type = store_type or settings.VECTOR_STORE_TYPE
        
        # 检查是否支持指定的向量数据库类型
        if vector_store_type not in cls._store_types:
            supported_types = list(cls._store_types.keys())
            raise ValueError(f"不支持的向量数据库类型: {vector_store_type}，支持的类型: {supported_types}")
        
        # 单例模式：如果已有实例，直接返回
        instance_key = f"{vector_store_type}_{hash(str(config)) if config else 'default'}"
        if instance_key in cls._instances:
            logger.debug(f"使用缓存的向量数据库实例: {vector_store_type}")
            return cls._instances[instance_key]
        
        # 创建新的向量数据库实例
        logger.info(f"创建新的向量数据库实例: {vector_store_type}")
        store_class = cls._store_types[vector_store_type]
        
        if config:
            instance = store_class(**config)
        else:
            instance = store_class()
        
        # 缓存实例
        cls._instances[instance_key] = instance
        return instance
    
    @classmethod
    def register_store_type(cls, name: str, store_class: Type[VectorStoreBase]) -> None:
        """
        注册新的向量数据库类型
        
        Args:
            name: 向量数据库类型名称
            store_class: 向量数据库实现类
        """
        if name in cls._store_types:
            logger.warning(f"覆盖已存在的向量数据库类型: {name}")
        
        cls._store_types[name] = store_class
        logger.info(f"注册向量数据库类型: {name}")
    
    @classmethod
    def list_supported_types(cls) -> list:
        """
        列出所有支持的向量数据库类型
        
        Returns:
            list: 支持的向量数据库类型列表
        """
        return list(cls._store_types.keys())
    
    @classmethod
    def clear_instances(cls) -> None:
        """
        清除所有缓存的向量数据库实例
        """
        for instance in cls._instances.values():
            try:
                import asyncio
                asyncio.run(instance.close())
            except Exception as e:
                logger.error(f"关闭向量数据库实例失败: {str(e)}")
        
        cls._instances.clear()
        logger.info("清除所有向量数据库实例缓存") 