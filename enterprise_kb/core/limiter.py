"""速率限制配置模块"""
from fastapi import FastAPI
import redis.asyncio as redis
from slowapi import Limiter
from slowapi.util import get_remote_address

from enterprise_kb.core.config.settings import settings


def setup_limiter(app: FastAPI) -> None:
    """设置速率限制器，在应用启动时调用"""
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    
    @app.lifespan
    async def lifespan(app: FastAPI):
        """使用lifespan管理限速器的生命周期"""
        # 初始化限速器（启动时）
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[
                f"{settings.RATE_LIMIT_MINUTE}/minute",
                f"{settings.RATE_LIMIT_HOUR}/hour",
                f"{settings.RATE_LIMIT_DAY}/day",
            ],
            storage_uri=settings.REDIS_URL,
        )
        app.state.limiter = limiter
        
        yield
        
        # 关闭Redis连接（关闭时）
        await redis_client.close()


# 默认限速器
default_rate_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[
        f"{settings.RATE_LIMIT_MINUTE}/minute",
        f"{settings.RATE_LIMIT_HOUR}/hour",
        f"{settings.RATE_LIMIT_DAY}/day",
    ],
    storage_uri=settings.REDIS_URL,
) 