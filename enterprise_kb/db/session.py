"""数据库会话模块"""
from contextvars import ContextVar
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from enterprise_kb.core.config.settings import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # 使用DEBUG代替DB_ECHO
    future=True,
    # 使用默认值，以防设置中没有这些属性
    pool_size=getattr(settings, "DB_POOL_SIZE", 5),
    max_overflow=getattr(settings, "DB_MAX_OVERFLOW", 10)
)

# 创建会话工厂
async_session_factory = async_sessionmaker(
    engine, 
    expire_on_commit=False,
    class_=AsyncSession
)

# 上下文变量，用于存储当前请求的会话
session_context = ContextVar("session_context", default=None)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话
    
    Yields:
        数据库会话
    """
    session = async_session_factory()
    try:
        # 将会话存储到上下文变量
        token = session_context.set(session)
        yield session
    finally:
        session_context.reset(token)
        await session.close()

def get_current_session() -> AsyncSession:
    """
    获取当前上下文的会话
    
    Returns:
        当前会话，如果不存在则创建新会话
    """
    session = session_context.get()
    if session is None:
        session = async_session_factory()
        session_context.set(session)
    return session 