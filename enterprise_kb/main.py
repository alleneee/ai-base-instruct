"""企业知识库平台主应用入口"""
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uvicorn

# 导入路由
from enterprise_kb.api.documents_extended import router as documents_router
from enterprise_kb.api.datasources import router as datasources_router
from enterprise_kb.api.retrieval import router as retrieval_router
from enterprise_kb.api.ragflow import router as ragflow_router

# 导入配置
from enterprise_kb.core.config.settings import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    description="企业知识库平台API，提供文档管理、向量检索和RAGFlow集成功能",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求计时中间件
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """记录请求处理时间的中间件"""
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # 记录请求信息
        logger.info(
            f"Path: {request.url.path} | "
            f"Method: {request.method} | "
            f"Time: {process_time:.4f}s"
        )
        return response
    except Exception as e:
        # 记录异常
        logger.error(
            f"Path: {request.url.path} | "
            f"Method: {request.method} | "
            f"Error: {str(e)}"
        )
        
        # 返回错误响应
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误"}
        )

# 注册路由
app.include_router(documents_router, prefix=settings.API_PREFIX)
app.include_router(datasources_router, prefix=settings.API_PREFIX)
app.include_router(retrieval_router, prefix=settings.API_PREFIX)
app.include_router(ragflow_router, prefix=settings.API_PREFIX)

@app.get("/")
async def root():
    """应用根路径响应"""
    return {"message": f"欢迎使用{settings.APP_NAME}"}

@app.get("/api/health")
async def health_check():
    """应用健康检查"""
    return {"status": "healthy", "version": "1.0.0"}

@app.on_event("startup")
async def startup_event():
    """应用启动事件处理"""
    logger.info("应用启动...")
    
    # 在这里可以添加应用启动时的初始化代码
    # 例如：初始化数据库连接、加载默认数据源等
    
    logger.info(f"{settings.APP_NAME}已成功启动")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件处理"""
    logger.info("应用关闭...")
    
    # 在这里可以添加应用关闭时的清理代码
    # 例如：关闭数据库连接、释放资源等
    
    logger.info(f"{settings.APP_NAME}已安全关闭")

# 直接运行该文件时启动服务
if __name__ == "__main__":
    uvicorn.run(
        "enterprise_kb.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    ) 