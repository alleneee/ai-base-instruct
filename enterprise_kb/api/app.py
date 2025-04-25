"""FastAPI应用配置模块"""
import logging
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from enterprise_kb.api.middlewares.timing import add_process_time_header
from enterprise_kb.api.router import api_router
from enterprise_kb.core.config.settings import settings
from enterprise_kb.core.config.logging import configure_logging
from enterprise_kb.core.cache import setup_cache
from enterprise_kb.core.limiter import setup_limiter
from enterprise_kb.core.pagination import setup_pagination

# 配置日志
configure_logging()
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    description="企业级知识库平台API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求处理中间件
app.middleware("http")(add_process_time_header)

# 全局异常处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """处理请求验证错误"""
    errors = []
    for error in exc.errors():
        errors.append({
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors}
    )

# 设置缓存
setup_cache(app)

# 设置速率限制
setup_limiter(app)

# 设置分页
setup_pagination(app)

# 注册路由
app.include_router(api_router)

# 根路由
@app.get("/", tags=["状态"])
async def root():
    """API根路由，返回API状态"""
    return {
        "name": settings.APP_NAME,
        "status": "online",
        "version": "1.0.0"
    }

# 健康检查
@app.get("/health", tags=["状态"])
async def health():
    """健康检查路由"""
    return {"status": "ok"} 