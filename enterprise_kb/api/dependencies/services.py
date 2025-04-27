"""依赖注入模块，用于提供各种服务的依赖"""
from fastapi import Depends
from typing import Callable, Type, TypeVar

from enterprise_kb.db.repositories.document_repository import DocumentRepository
from enterprise_kb.services.document_service import DocumentService
from enterprise_kb.services.search_service import SearchService
from enterprise_kb.core.document_processor import get_document_processor

T = TypeVar('T')

# 仓库依赖
def get_document_repository() -> DocumentRepository:
    """获取文档仓库实例"""
    return DocumentRepository()

# 服务依赖
def get_document_service(
    doc_repo: DocumentRepository = Depends(get_document_repository)
) -> DocumentService:
    """获取文档服务实例"""
    return DocumentService(doc_repo)

def get_search_service() -> SearchService:
    """获取搜索服务实例"""
    return SearchService()

# 文档处理器依赖
def get_processor():
    """获取文档处理器实例"""
    return get_document_processor()

# 通用服务工厂
def service_factory(service_class: Type[T]) -> Callable[[], T]:
    """
    创建服务实例的工厂函数
    
    Args:
        service_class: 服务类
        
    Returns:
        返回一个函数，该函数返回服务实例
    """
    def get_service() -> T:
        return service_class()
    return get_service 