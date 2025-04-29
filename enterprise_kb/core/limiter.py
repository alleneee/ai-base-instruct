"""速率限制配置模块"""
from fastapi import FastAPI
import redis.asyncio as redis
from slowapi import Limiter
from slowapi.util import get_remote_address

from enterprise_kb.core.config.settings import settings


def setup_limiter(app: FastAPI) -> None:
    """设置速率限制器，在应用启动时调用"""
    # 创建Redis客户端
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    
    # 初始化限速器
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[
            f"{settings.RATE_LIMIT_SECOND}/second",
        ],
        storage_uri=settings.REDIS_URL,
    )
    
    # 设置到app状态中
    app.state.limiter = limiter
    
    # 初始化函数
    async def init_limiter():
        """初始化限速器"""
        # 已在外部初始化limiter
        pass
    
    # 清理函数
    async def close_limiter():
        """清理限速器资源"""
        await redis_client.close()
    
    # 将初始化和清理函数附加到app的state上
    app.state.init_limiter = init_limiter
    app.state.close_limiter = close_limiter


# 默认限速器
default_rate_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[
        f"{settings.RATE_LIMIT_SECOND}/second",
    ],
    storage_uri=settings.REDIS_URL,
) 