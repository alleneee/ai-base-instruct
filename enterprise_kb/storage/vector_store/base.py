"""
向量数据库抽象接口模块
提供统一的向量数据库操作接口，实现不同向量数据库的无缝切换
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import numpy as np


class VectorStoreBase(ABC):
    """
    向量数据库抽象基类
    
    定义了所有向量数据库实现必须支持的核心操作接口
    """
    
    @abstractmethod
    async def initialize(self) -> None:
        """初始化向量数据库连接和设置"""
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def drop_collection(self, collection_name: str) -> bool:
        """
        删除向量集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 删除是否成功
        """
        pass
    
    @abstractmethod
    async def has_collection(self, collection_name: str) -> bool:
        """
        检查集合是否存在
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 集合是否存在
        """
        pass
    
    @abstractmethod
    async def list_collections(self) -> List[str]:
        """
        列出所有集合名称
        
        Returns:
            List[str]: 集合名称列表
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def delete(self, collection_name: str, ids: List[str]) -> bool:
        """
        删除指定ID的向量
        
        Args:
            collection_name: 集合名称
            ids: 要删除的向量ID列表
            
        Returns:
            bool: 删除是否成功
        """
        pass
    
    @abstractmethod
    async def count(self, collection_name: str, filter_expr: Optional[str] = None) -> int:
        """
        计算集合中的向量数量
        
        Args:
            collection_name: 集合名称
            filter_expr: 过滤表达式
            
        Returns:
            int: 向量数量
        """
        pass
    
    @abstractmethod
    async def get(self, collection_name: str, ids: List[str]) -> List[Dict[str, Any]]:
        """
        获取指定ID的向量
        
        Args:
            collection_name: 集合名称
            ids: 向量ID列表
            
        Returns:
            List[Dict[str, Any]]: 向量数据列表，包含id、vector和metadata
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭向量数据库连接"""
        pass