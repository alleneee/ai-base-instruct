import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import time

from enterprise_kb.config.settings import settings
from enterprise_kb.api.document_routes import router as document_router
from enterprise_kb.api.search_routes import router as search_router
from enterprise_kb.api.auth_routes import router as auth_router
from enterprise_kb.core.cache import setup_cache
from enterprise_kb.core.limiter import setup_limiter
from enterprise_kb.core.pagination import setup_pagination

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
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """添加请求处理时间头"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# 全局异常处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
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
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(document_router, prefix=settings.API_PREFIX)
app.include_router(search_router, prefix=settings.API_PREFIX)

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