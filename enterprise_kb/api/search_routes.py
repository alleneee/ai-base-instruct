import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_kb.config.database import get_async_session
from enterprise_kb.core.cache import cached
from enterprise_kb.core.limiter import default_rate_limiter
from enterprise_kb.models.schemas import (
    SearchRequest, SearchResponse, ErrorResponse
)
from enterprise_kb.models.users import User, current_active_user
from enterprise_kb.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["知识检索"],
    responses={
        500: {"model": ErrorResponse, "description": "服务器内部错误"}
    }
)

# 依赖注入
async def get_search_service(session: AsyncSession = Depends(get_async_session)):
    """获取搜索服务实例"""
    return SearchService(session)

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
    search_service: SearchService = Depends(get_search_service),
    user: User = Depends(current_active_user)
):
    """执行知识检索"""
    try:
        result = await search_service.search(
            search_request, 
            user_id=str(user.id)
        )
        return result
    except Exception as e:
        logger.error(f"检索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

@router.get(
    "/health",
    summary="检索服务健康检查",
    description="检查检索服务是否正常运行"
)
async def health_check(
    search_service: SearchService = Depends(get_search_service)
):
    """检索服务健康检查"""
    try:
        # 这里可以添加实际的健康检查逻辑
        return {"status": "ok", "message": "检索服务正常运行"}
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}") 