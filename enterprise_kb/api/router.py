"""主路由集合模块"""
from fastapi import APIRouter

from enterprise_kb.api.endpoints.auth import router as auth_router
from enterprise_kb.api.endpoints.documents import router as document_router
from enterprise_kb.api.endpoints.search import router as search_router
from enterprise_kb.api.endpoints.datasources import router as datasource_router
# 导入V1版本API路由
from enterprise_kb.api.v1.router import api_router_v1
from enterprise_kb.core.config.settings import settings

# 创建主路由
api_router = APIRouter()

# 注册子路由
api_router.include_router(auth_router, prefix=settings.API_PREFIX)
api_router.include_router(document_router, prefix=settings.API_PREFIX)
api_router.include_router(search_router, prefix=settings.API_PREFIX)
api_router.include_router(datasource_router, prefix=settings.API_PREFIX)

# 注册V1版本API路由
api_router.include_router(api_router_v1, prefix="/api/v1") 