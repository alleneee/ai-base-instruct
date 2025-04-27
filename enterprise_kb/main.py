"""企业知识库平台主应用入口"""
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
import time
import uvicorn

# 导入路由
from enterprise_kb.api.documents_extended import router as documents_router
from enterprise_kb.api.datasources import router as datasources_router
from enterprise_kb.api.retrieval import router as retrieval_router
from enterprise_kb.api.ragflow import router as ragflow_router
from enterprise_kb.api.celery_tasks import router as celery_router
from enterprise_kb.api.celery_tasks_v2 import router as celery_v2_router
from enterprise_kb.api.query_rewriting import router as query_rewriting_router
from enterprise_kb.api.document_segment_api import router as document_segment_router

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
    description="""
    # 企业知识库平台API文档
    
    本平台提供了一套完整的企业级知识库API，支持文档处理、向量检索和RAGFlow集成功能。
    
    ## 主要功能
    
    * **文档管理**：支持多种格式文档的上传、处理和管理
    * **智能文档分析**：自动分析文档特征，选择最佳处理路径
    * **向量检索**：支持向量搜索、关键词搜索和混合搜索
    * **RAGFlow集成**：与RAGFlow无缝集成，实现高级检索增强生成
    
    ## 认证方式
    
    大部分API需要通过JWT令牌认证，在请求头中添加`Authorization: Bearer {token}`。
    
    ## 错误处理
    
    所有API返回的错误遵循统一格式:
    ```json
    {
      "code": 错误代码,
      "message": "错误描述信息",
      "details": "详细错误信息（可选）"
    }
    ```
    
    ## 速率限制
    
    为保证服务质量，API实施了速率限制，默认为每秒10个请求。
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={
        "name": "技术支持团队",
        "url": "https://example.com/support",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT许可证",
        "url": "https://opensource.org/licenses/MIT",
    },
    terms_of_service="https://example.com/terms/",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应限制为特定域名
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
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """处理HTTP异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """处理通用异常"""
    logger.error(f"未处理的异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "details": str(exc) if settings.DEBUG else None
        }
    )

# 注册路由
app.include_router(documents_router, prefix=settings.API_PREFIX)
app.include_router(datasources_router, prefix=settings.API_PREFIX)
app.include_router(retrieval_router, prefix=settings.API_PREFIX)
app.include_router(ragflow_router, prefix=settings.API_PREFIX)
app.include_router(query_rewriting_router)  # 查询重写路由
app.include_router(celery_router)
app.include_router(celery_v2_router)  # 改进的Celery任务API
app.include_router(document_segment_router)  # 文档分段处理API

@app.get("/", 
    tags=["系统状态"], 
    summary="获取API状态",
    description="返回API服务的基本状态信息，可用于检查API是否正常运行",
    response_description="API状态信息",
    responses={
        200: {
            "description": "成功响应",
            "content": {
                "application/json": {
                    "example": {
                        "message": "欢迎使用企业知识库平台",
                        "version": "1.0.0",
                        "status": "online"
                    }
                }
            }
        }
    }
)
async def root():
    """应用根路径响应"""
    return {
        "message": f"欢迎使用{settings.APP_NAME}",
        "version": "1.0.0",
        "status": "online"
    }

@app.get("/api/health", 
    tags=["系统状态"], 
    summary="健康检查端点",
    description="用于监控和负载均衡的健康检查端点",
    response_description="健康状态",
    responses={
        200: {
            "description": "服务健康",
            "content": {
                "application/json": {
                    "example": {"status": "healthy"}
                }
            }
        },
        503: {
            "description": "服务不健康",
            "content": {
                "application/json": {
                    "example": {"status": "unhealthy", "details": "数据库连接失败"}
                }
            }
        }
    }
)
async def health_check():
    """健康检查端点"""
    # 可以在这里添加数据库连接检查等健康检查逻辑
    return {"status": "healthy"}

# 自定义OpenAPI生成
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        contact=app.contact,
        license_info=app.license_info,
        terms_of_service=app.terms_of_service,
    )
    
    # 添加安全模式
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "使用JWT令牌进行身份验证，格式: Bearer {token}"
        }
    }
    
    # 设置全局安全要求
    openapi_schema["security"] = [{"BearerAuth": []}]
    
    # 添加标签描述
    openapi_schema["tags"] = [
        {
            "name": "文档管理",
            "description": "文档上传、处理和管理相关操作",
            "externalDocs": {
                "description": "更多关于文档管理的信息",
                "url": "https://example.com/docs/documents",
            },
        },
        {
            "name": "数据源管理",
            "description": "管理知识库的数据源",
        },
        {
            "name": "检索服务",
            "description": "提供向量检索和语义搜索功能",
        },
        {
            "name": "RAGFlow集成",
            "description": "与RAGFlow平台集成的接口",
        },
        {
            "name": "系统状态",
            "description": "系统健康检查和状态监控接口",
        },
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# 自定义文档页面
@app.get("/api/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title=f"{app.title} - API文档",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="/static/favicon.png",
        swagger_ui_parameters={"docExpansion": "none", "defaultModelsExpandDepth": -1}
    )

@app.get("/api/redoc", include_in_schema=False)
async def custom_redoc_html():
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title=f"{app.title} - ReDoc文档",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js",
        redoc_favicon_url="/static/favicon.png",
        with_google_fonts=False
    )

if __name__ == "__main__":
    uvicorn.run("enterprise_kb.main:app", host="0.0.0.0", port=8000, reload=True)