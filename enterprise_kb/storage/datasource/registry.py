"""数据源注册表模块，管理所有可用的数据源类型"""
from typing import Dict, Type, Optional
import logging

from enterprise_kb.storage.datasource.base import DataSource

logger = logging.getLogger(__name__)

# 数据源类型注册表
_DATASOURCE_REGISTRY: Dict[str, Type[DataSource]] = {}


def register_datasource(source_type: str):
    """数据源注册装饰器
    
    Args:
        source_type: 数据源类型标识
        
    Returns:
        装饰器函数
    """
    def decorator(cls: Type[DataSource]):
        if source_type in _DATASOURCE_REGISTRY:
            logger.warning(f"数据源类型 {source_type} 已存在，将被覆盖")
        
        # 设置类的source_type属性
        cls.source_type = source_type
        # 注册数据源类
        _DATASOURCE_REGISTRY[source_type] = cls
        logger.debug(f"注册数据源类型: {source_type}")
        return cls
    
    return decorator


def get_datasource_class(source_type: str) -> Optional[Type[DataSource]]:
    """获取数据源类
    
    Args:
        source_type: 数据源类型标识
        
    Returns:
        数据源类，如果不存在则返回None
    """
    return _DATASOURCE_REGISTRY.get(source_type)


def list_datasource_types() -> Dict[str, str]:
    """列出所有注册的数据源类型
    
    Returns:
        数据源类型字典，键为类型标识，值为描述信息
    """
    return {
        source_type: cls.__doc__ or "无描述"
        for source_type, cls in _DATASOURCE_REGISTRY.items()
    } 