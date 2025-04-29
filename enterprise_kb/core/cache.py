"""缓存配置模块"""
from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
import redis

from enterprise_kb.core.config.settings import settings


def setup_cache(app: FastAPI) -> None:
    """设置缓存，在应用启动时调用"""
    # 创建Redis客户端
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    
    # 初始化函数
    async def init_cache():
        """初始化缓存"""
        FastAPICache.init(
            RedisBackend(redis_client), 
            prefix="enterprise_kb_cache",
            expire=settings.CACHE_EXPIRE,
        )
    
    # 清理函数
    async def close_cache():
        """清理缓存资源"""
        # 标准Redis库使用同步close方法，不是异步的
        redis_client.close()
    
    # 将初始化和清理函数附加到app的state上
    app.state.init_cache = init_cache
    app.state.close_cache = close_cache


# 导出缓存装饰器以便在路由中使用
cached = cache 