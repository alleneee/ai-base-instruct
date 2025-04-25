"""数据库基础设置模块"""
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

from enterprise_kb.core.config.settings import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=settings.DEBUG,
    future=True,
)

# 声明基类
Base = declarative_base() 