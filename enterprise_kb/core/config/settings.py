import os
from typing import Optional, Dict, Any, List, Union, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pydantic import validator, Field

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "企业知识库平台"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # LlamaIndex配置
    LLAMA_INDEX_CHUNK_SIZE: int = 1024
    LLAMA_INDEX_CHUNK_OVERLAP: int = 20

    # Milvus配置
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_COLLECTION: str = os.getenv("MILVUS_COLLECTION", "enterprise_kb")
    MILVUS_DIMENSION: int = 1536  # 默认嵌入向量维度

    # Milvus新配置
    MILVUS_URI: str = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
    MILVUS_USER: str = os.getenv("MILVUS_USER", "")
    MILVUS_PASSWORD: str = os.getenv("MILVUS_PASSWORD", "")
    MILVUS_TEXT_FIELD: str = os.getenv("MILVUS_TEXT_FIELD", "text")
    MILVUS_EMBEDDING_FIELD: str = os.getenv("MILVUS_EMBEDDING_FIELD", "embedding")
    MILVUS_METADATA_FIELD: str = os.getenv("MILVUS_METADATA_FIELD", "metadata")
    MILVUS_ID_FIELD: str = os.getenv("MILVUS_ID_FIELD", "id")

    # PostgreSQL配置
    POSTGRES_CONNECTION_STRING: str = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_kb")
    POSTGRES_SCHEMA_NAME: str = os.getenv("POSTGRES_SCHEMA_NAME", "public")
    POSTGRES_TABLE_NAME: str = os.getenv("POSTGRES_TABLE_NAME", "kb_vectors")
    POSTGRES_VECTOR_COLUMN: str = os.getenv("POSTGRES_VECTOR_COLUMN", "embedding")
    POSTGRES_CONTENT_COLUMN: str = os.getenv("POSTGRES_CONTENT_COLUMN", "content")
    POSTGRES_METADATA_COLUMN: str = os.getenv("POSTGRES_METADATA_COLUMN", "metadata")
    POSTGRES_DIMENSION: int = int(os.getenv("POSTGRES_DIMENSION", "1536"))

    # MySQL数据库配置
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "password")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "enterprise_kb")
    MYSQL_URL: str = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

    # 文档处理配置
    UPLOAD_DIR: str = "data/uploads"
    PROCESSED_DIR: str = "data/processed"
    SUPPORTED_DOCUMENT_TYPES: List[str] = [
        ".pdf", ".docx", ".doc", ".txt", ".md",
        ".ppt", ".pptx", ".csv", ".xlsx", ".xls"
    ]

    # 数据库配置
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_kb"
    )

    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 天
    JWT_ALGORITHM: str = "HS256"

    # 鉴权配置
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    AUTH_TOKEN_URL: str = "/api/v1/auth/token"
    AUTH_PUBLIC_ENDPOINTS: List[str] = [
        "/api/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
        "/api/v1/auth/token",
        "/api/v1/auth/register"
    ]

    # 邮件配置
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "noreply@example.com")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", "587"))
    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "")
    MAIL_FROM_NAME: str = os.getenv("MAIL_FROM_NAME", "企业知识库平台")
    MAIL_TLS: bool = True
    MAIL_SSL: bool = False

    # Redis配置（用于缓存和限速）
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )

    # 缓存配置
    CACHE_EXPIRE: int = 60 * 15  # 15分钟

    # API限流配置
    RATE_LIMIT_SECOND: int = 10  # 每秒请求数量限制

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # CORS配置
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # Celery配置
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")
    CELERY_ALWAYS_EAGER: bool = Field(default=False)  # 设置为True时会同步执行任务，便于调试
    CELERY_TASK_TIME_LIMIT: int = Field(default=3600)  # 任务硬时间限制（秒）
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=3300)  # 任务软时间限制（秒）
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(default=200)  # 每个worker子进程处理的最大任务数
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = Field(default=4)  # worker预取任务数乘数
    CELERY_TASK_ACKS_LATE: bool = Field(default=True)  # 任务完成后再确认
    CELERY_RESULT_EXPIRES: int = Field(default=86400 * 7)  # 结果过期时间（秒）
    CELERY_WORKER_CONCURRENCY: int = Field(default=None)  # worker并发数，None表示使用CPU核心数
    CELERY_TASK_DEFAULT_RATE_LIMIT: str = Field(default="100/m")  # 默认任务速率限制
    CELERY_TASK_EAGER_PROPAGATES: bool = Field(default=True)  # 同步模式下传播异常

    # 文档处理配置
    MAX_CONCURRENT_TASKS: int = Field(default=10)
    DOCUMENT_CHUNK_SIZE: int = Field(default=500)
    DOCUMENT_CHUNK_OVERLAP: int = Field(default=50)

    # 并行处理配置
    PARALLEL_PROCESSING_ENABLED: bool = Field(default=True)
    PARALLEL_MAX_WORKERS: int = Field(default=None)  # None表示使用CPU核心数
    PARALLEL_CHUNK_SIZE: int = Field(default=100000)  # 并行处理的块大小（字符数）
    PARALLEL_CHUNK_STRATEGY: str = Field(default="sentence")  # 分块策略：fixed_size, sentence, paragraph, semantic
    PARALLEL_USE_DISTRIBUTED: bool = Field(default=False)  # 是否使用分布式处理(Celery)
    PARALLEL_MEMORY_EFFICIENT: bool = Field(default=False)  # 是否使用内存高效模式
    PARALLEL_BATCH_SIZE: int = Field(default=10)  # 批处理大小，用于内存优化

    # 语义分块配置
    SEMANTIC_CHUNKING_ENABLED: bool = Field(default=True)
    SEMANTIC_CHUNKING_TYPE: str = Field(default="hierarchical")  # semantic, hierarchical
    SEMANTIC_RESPECT_MARKDOWN: bool = Field(default=True)

    # 增量更新配置
    INCREMENTAL_PROCESSING_ENABLED: bool = Field(default=True)
    INCREMENTAL_FORCE_REPROCESS_THRESHOLD: float = Field(default=0.5)  # 超过此比例的变化时强制重新处理

    # 索引配置
    DEFAULT_INDEX_TYPE: str = Field(default="vector")
    INDEX_REFRESH_INTERVAL: int = Field(default=86400)  # 每天刷新一次索引，单位为秒

    # 查询重写配置
    QUERY_REWRITE_ENABLED: bool = Field(default=True)  # 是否启用查询重写
    QUERY_REWRITE_MODEL: str = Field(default="gpt-3.5-turbo")  # 用于查询重写的模型
    QUERY_REWRITE_VARIANTS: int = Field(default=3)  # 每个查询生成的变体数量
    QUERY_REWRITE_CACHE_SIZE: int = Field(default=1000)  # 查询重写缓存大小

    # 项目名称
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "enterprise-kb")

    # 令牌计数设置
    TOKEN_COUNTING_ENABLED: bool = os.getenv("TOKEN_COUNTING_ENABLED", "True").lower() in ("true", "1", "yes")
    TOKEN_COUNTING_VERBOSE: bool = os.getenv("TOKEN_COUNTING_VERBOSE", "False").lower() in ("true", "1", "yes")
    TOKEN_COUNTER_MODEL: str = os.getenv("TOKEN_COUNTER_MODEL", "gpt-3.5-turbo")

    # Milvus索引管理设置
    MILVUS_INDEX_MANAGEMENT: str = os.getenv("MILVUS_INDEX_MANAGEMENT", "CREATE_IF_NOT_EXISTS")  # 可选：NO_VALIDATION, CREATE_IF_NOT_EXISTS
    MILVUS_OVERWRITE: bool = os.getenv("MILVUS_OVERWRITE", "False").lower() in ("true", "1", "yes")

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """处理CORS来源"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """获取应用设置的缓存实例"""
    return Settings()

settings = get_settings()

# 确保存储目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
os.makedirs(os.path.join(settings.PROCESSED_DIR, "markdown"), exist_ok=True)