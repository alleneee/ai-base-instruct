"""
数据库连接配置

此模块提供数据库连接和会话管理功能
"""
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from enterprise_kb.core.config.settings import settings

# 创建数据库引擎
engine = create_engine(
    settings.MYSQL_URL,
    pool_pre_ping=True,  # 每次连接前ping一下数据库，确保连接有效
    pool_recycle=3600,   # 一小时后回收连接
    pool_size=5,        # 连接池大小
    max_overflow=10,    # 允许的最大溢出连接数
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类模型
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    提供数据库会话的依赖函数
    
    Yields:
        Generator[Session, None, None]: 数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_db():
    """初始化数据库，创建所有表"""
    async with engine.begin() as conn:
        # 仅在开发环境下自动创建表
        if settings.DEBUG:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("数据库表已创建")
        
async def close_db_connection():
    """关闭数据库连接"""
    await engine.dispose()
    logger.info("数据库连接已关闭") 