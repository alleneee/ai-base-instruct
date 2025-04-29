import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from enterprise_kb.core.config.settings import settings

# 创建SQLAlchemy基础模型类
Base = declarative_base()

# 配置日志
logger = logging.getLogger(__name__)

# 创建异步引擎
# 使用URL格式: mysql+aiomysql://user:password@host:port/dbname
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖注入函数，用于FastAPI路由
    
    使用示例:
    ```
    @router.get("/items")
    async def get_items(db: AsyncSession = Depends(get_db)):
        items = await crud.get_items(db)
        return items
    ```
    """
    async with async_session_factory() as session:
        logger.debug("获取数据库会话")
        try:
            yield session
        finally:
            await session.close()
            logger.debug("关闭数据库会话")


async def create_database_tables() -> None:
    """
    创建所有数据库表（如果不存在）
    仅在开发环境中使用，生产环境应使用Alembic迁移
    """
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表已创建")


async def drop_database_tables() -> None:
    """
    删除所有数据库表
    警告：仅在开发/测试环境中使用
    """
    async with engine.begin() as conn:
        # 删除所有表
        await conn.run_sync(Base.metadata.drop_all)
        logger.warning("数据库表已删除")


# 用于测试的同步会话创建函数
def get_test_db_session():
    """
    获取测试用同步数据库会话
    仅用于测试目的，不用于生产代码
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # 使用同步引擎，通常使用SQLite内存数据库进行测试
    test_engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    Base.metadata.create_all(bind=test_engine)
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close() 