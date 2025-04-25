"""搜索端点模块"""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_kb.core.auth import User, current_active_user
from enterprise_kb.core.cache import cached
from enterprise_kb.core.limiter import default_rate_limiter
from enterprise_kb.db.session import get_async_session
from enterprise_kb.schemas.search import SearchRequest, SearchResponse
from enterprise_kb.schemas.auth import ErrorResponse
from enterprise_kb.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["知识检索"],
    responses={
        500: {"model": ErrorResponse, "description": "服务器内部错误"}
    }
)

@router.post(
    "",
    response_model=SearchResponse,
    summary="知识检索",
    description="根据查询文本检索相关知识",
    dependencies=[Depends(default_rate_limiter)]
)
@cached(expire=60 * 5)  # 缓存5分钟
async def search(
    search_request: SearchRequest,
    user: User = Depends(current_active_user)
):
    """执行知识检索"""
    try:
        service = SearchService()
        result = await service.search(search_request)
        return result
    except Exception as e:
        logger.error(f"检索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

@router.get(
    "/datasources",
    response_model=List[str],
    summary="获取所有可用的数据源",
    description="返回系统中所有已配置的数据源名称列表"
)
async def list_datasources(
    user: User = Depends(current_active_user)
):
    """获取所有可用的数据源"""
    try:
        service = SearchService()
        return await service.list_datasources()
    except Exception as e:
        logger.error(f"获取数据源列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取数据源列表失败: {str(e)}")

@router.get(
    "/health",
    summary="检索服务健康检查",
    description="检查检索服务是否正常运行"
)
async def health_check():
    """检索服务健康检查"""
    try:
        # 这里可以添加实际的健康检查逻辑
        return {"status": "ok", "message": "检索服务正常运行"}
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}") 