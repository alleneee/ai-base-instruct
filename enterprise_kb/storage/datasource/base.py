"""数据源基类模块，定义数据源抽象接口"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic, Type
from pydantic import BaseModel, Field, ConfigDict


class DataSourceConfig(BaseModel):
    """数据源配置基类"""
    
    name: str = Field(..., description="数据源名称")
    description: Optional[str] = Field(None, description="数据源描述")
    
    model_config = ConfigDict(extra="allow")


T = TypeVar('T', bound=DataSourceConfig)


class DataSource(Generic[T], ABC):
    """数据源抽象基类"""
    
    source_type: str = "base"
    
    def __init__(self, config: T):
        """初始化数据源
        
        Args:
            config: 数据源配置
        """
        self.config = config
        self._validate_config()
        self._initialize()
    
    def _validate_config(self) -> None:
        """验证配置有效性"""
        pass
    
    def _initialize(self) -> None:
        """初始化数据源连接和资源"""
        pass
    
    @abstractmethod
    async def connect(self) -> None:
        """连接到数据源"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """断开与数据源的连接"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """检查数据源健康状态
        
        Returns:
            数据源是否健康
        """
        pass
    
    @abstractmethod
    async def get_info(self) -> Dict[str, Any]:
        """获取数据源信息
        
        Returns:
            数据源信息字典
        """
        pass


class DataSourceFactory:
    """数据源工厂，负责创建不同类型的数据源实例"""
    
    @staticmethod
    def create(source_type: str, config: Dict[str, Any]) -> DataSource:
        """创建数据源实例
        
        Args:
            source_type: 数据源类型
            config: 数据源配置
            
        Returns:
            数据源实例
            
        Raises:
            ValueError: 不支持的数据源类型
        """
        from enterprise_kb.storage.datasource.registry import get_datasource_class
        
        # 获取数据源类
        datasource_class = get_datasource_class(source_type)
        if not datasource_class:
            raise ValueError(f"不支持的数据源类型: {source_type}")
        
        # 创建配置实例
        config_class = datasource_class.get_config_class()
        config_instance = config_class(**config)
        
        # 创建数据源实例
        return datasource_class(config_instance) 