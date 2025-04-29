"""依赖注入模块，用于提供各种服务的依赖"""
from functools import lru_cache
from typing import Callable, Type, TypeVar, AsyncGenerator, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_kb.db.repositories.document_repository import DocumentRepository
from enterprise_kb.services.document_service import DocumentService
from enterprise_kb.services.search_service import SearchService
from enterprise_kb.core.document_processor import get_document_processor
from enterprise_kb.config.database import get_async_session

T = TypeVar('T')

# 数据库会话依赖
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with get_async_session() as session:
        yield session

# 仓库依赖
async def get_document_repository(
    session: AsyncSession = Depends(get_db_session)
) -> DocumentRepository:
    """获取文档仓库实例"""
    return DocumentRepository(session)

# 服务依赖 - 使用缓存提高性能
@lru_cache(maxsize=32)
def get_document_processor_cached():
    """获取缓存的文档处理器实例"""
    return get_document_processor()

# 服务依赖
async def get_document_service(
    doc_repo: DocumentRepository = Depends(get_document_repository)
) -> DocumentService:
    """获取文档服务实例"""
    return DocumentService(doc_repo)

async def get_search_service(
    doc_repo: DocumentRepository = Depends(get_document_repository)
) -> SearchService:
    """获取搜索服务实例"""
    return SearchService(doc_repo)

# 文档处理器依赖
def get_processor():
    """获取文档处理器实例"""
    return get_document_processor_cached()

# 通用服务工厂
def service_factory(service_class: Type[T]) -> Callable[..., T]:
    """
    创建服务实例的工厂函数
    
    Args:
        service_class: 服务类
        
    Returns:
        返回一个函数，该函数返回服务实例
    """
    async def get_service(
        session: AsyncSession = Depends(get_db_session)
    ) -> T:
        return service_class(session)
    return get_service

# 类型注解简化
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
DocumentRepo = Annotated[DocumentRepository, Depends(get_document_repository)]
DocumentSvc = Annotated[DocumentService, Depends(get_document_service)]
SearchSvc = Annotated[SearchService, Depends(get_search_service)]
Processor = Annotated[object, Depends(get_processor)] 