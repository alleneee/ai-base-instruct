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
    
    @app.lifespan
    async def lifespan(app: FastAPI):
        """使用lifespan管理缓存的生命周期"""
        # 初始化缓存（启动时）
        FastAPICache.init(
            RedisBackend(redis_client), 
            prefix="enterprise_kb_cache",
            expire=settings.CACHE_EXPIRE,
        )
        
        yield
        
        # 关闭Redis连接（关闭时）
        await redis_client.close()


# 导出缓存装饰器以便在路由中使用
cached = cache 