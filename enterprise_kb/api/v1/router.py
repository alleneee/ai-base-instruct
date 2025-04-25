"""V1版本API路由模块"""
from fastapi import APIRouter

from enterprise_kb.api.v1.endpoints.users import router as users_router
from enterprise_kb.api.v1.endpoints.auth import router as auth_router
from enterprise_kb.api.v1.endpoints.datasets import router as datasets_router
from enterprise_kb.api.v1.endpoints.documents import router as documents_router
from enterprise_kb.api.v1.endpoints.chunks import router as chunks_router
from enterprise_kb.api.v1.endpoints.retrieval import router as retrieval_router
from enterprise_kb.api.v1.endpoints.chats import router as chats_router
from enterprise_kb.api.v1.endpoints.agents import router as agents_router
from enterprise_kb.api.v1.endpoints.openai_compat import router as openai_compat_router
from enterprise_kb.core.config.settings import settings

# 创建V1路由
api_router_v1 = APIRouter()

# 注册子路由
api_router_v1.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router_v1.include_router(users_router, prefix="/users", tags=["用户"])
api_router_v1.include_router(datasets_router)
api_router_v1.include_router(documents_router)
api_router_v1.include_router(chunks_router)
api_router_v1.include_router(retrieval_router)
api_router_v1.include_router(chats_router)
api_router_v1.include_router(agents_router)
api_router_v1.include_router(openai_compat_router) 