"""缓存配置模块"""
from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
import redis

from enterprise_kb.core.config.settings import settings


def setup_cache(app: FastAPI) -> None:
    """设置缓存，在应用启动时调用"""
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    
    @app.on_event("startup")
    async def startup():
        """应用启动时初始化缓存"""
        FastAPICache.init(
            RedisBackend(redis_client), 
            prefix="enterprise_kb_cache",
            expire=settings.CACHE_EXPIRE,
        )
        
    @app.on_event("shutdown")
    async def shutdown():
        """应用关闭时关闭Redis连接"""
        await redis_client.close()


# 导出缓存装饰器以便在路由中使用
cached = cache 