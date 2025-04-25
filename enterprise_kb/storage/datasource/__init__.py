"""数据源模块，提供多种数据源的统一接口"""

from enterprise_kb.storage.datasource.base import DataSource, DataSourceConfig, DataSourceFactory
from enterprise_kb.storage.datasource.registry import register_datasource, get_datasource_class

__all__ = [
    "DataSource", 
    "DataSourceConfig",
    "DataSourceFactory",
    "register_datasource", 
    "get_datasource_class"
] 