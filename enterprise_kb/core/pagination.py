"""分页配置模块"""
from fastapi import FastAPI, Query, Depends
from fastapi_pagination import Page, Params, add_pagination
from fastapi_pagination.links import Page as PageWithLinks
from typing import TypeVar, Generic, Sequence

from enterprise_kb.core.config.settings import settings

# 泛型类型变量
T = TypeVar("T")


# 自定义分页参数
def page_params(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
) -> Params:
    """获取分页参数"""
    return Params(page=page, size=size)


# 分页结果模型
class PaginatedResponse(Generic[T]):
    """分页响应模型"""
    def __init__(
        self, 
        items: Sequence[T], 
        total: int, 
        page: int, 
        size: int
    ):
        self.items = items
        self.total = total
        self.page = page
        self.size = size
        self.pages = (total + size - 1) // size if size > 0 else 0
        self.has_next = page < self.pages
        self.has_prev = page > 1


def setup_pagination(app: FastAPI) -> None:
    """设置分页，在应用启动时调用"""
    add_pagination(app) 