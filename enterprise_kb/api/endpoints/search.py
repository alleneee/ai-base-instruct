"""搜索API路由模块"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from enterprise_kb.api.dependencies import (
    SearchSvc, UserWithReadPerm, PaginationDep, response
)
from enterprise_kb.core.limiter import limiter_search
from enterprise_kb.core.cache import cached
from enterprise_kb.models.schemas import SearchQuery, SearchResult

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["搜索服务"],
    responses={
        404: {"description": "未找到资源"},
        500: {"description": "服务器内部错误"}
    }
)

class SearchFilters(BaseModel):
    """搜索过滤器"""
    source_id: Optional[str] = None
    file_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    is_relevant_only: bool = False

@router.post(
    "",
    response_model=SearchResult,
    summary="语义搜索",
    description="通过语义搜索查询文档"
)
@limiter_search
@cached(expire=30)  # 缓存30秒
async def semantic_search(
    query: SearchQuery,
    filters: Optional[SearchFilters] = None,
    pagination: PaginationDep = Depends(),
    search_service: SearchSvc = Depends(),
    user: UserWithReadPerm = Depends()
):
    """语义搜索接口"""
    try:
        filters_dict = {}
        if filters:
            filters_dict = filters.dict(exclude_none=True)
            
        results = await search_service.search(
            query=query.query,
            user_id=str(user.id),
            limit=pagination.size,
            offset=(pagination.page - 1) * pagination.size,
            **filters_dict
        )
        
        return results
    except Exception as e:
        logger.error(f"搜索操作失败: {str(e)}")
        return response.error(message=f"搜索操作失败: {str(e)}", status_code=500)
        
@router.get(
    "/related",
    response_model=List[str],
    summary="获取相关问题",
    description="根据输入的问题获取相关的问题建议"
)
@cached(expire=60)  # 缓存60秒
async def get_related_questions(
    question: str,
    limit: int = 5,
    search_service: SearchSvc = Depends(),
    user: UserWithReadPerm = Depends()
):
    """获取相关问题建议"""
    try:
        results = await search_service.get_related_questions(
            query=question,
            user_id=str(user.id),
            limit=limit
        )
        
        return results
    except Exception as e:
        logger.error(f"获取相关问题失败: {str(e)}")
        return response.error(message=f"获取相关问题失败: {str(e)}", status_code=500) 