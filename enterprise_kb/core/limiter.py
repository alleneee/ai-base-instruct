"""速率限制配置模块"""
from fastapi import FastAPI
import aioredis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from enterprise_kb.core.config.settings import settings


def setup_limiter(app: FastAPI) -> None:
    """设置速率限制，在应用启动时调用"""
    
    @app.on_event("startup")
    async def startup():
        """应用启动时初始化速率限制器"""
        redis = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await FastAPILimiter.init(redis)
        
    @app.on_event("shutdown")
    async def shutdown():
        """应用关闭时关闭Redis连接"""
        await FastAPILimiter.close()


# 默认限速器
default_rate_limiter = RateLimiter(
    times=settings.RATE_LIMIT_SECOND,
    seconds=1
) 